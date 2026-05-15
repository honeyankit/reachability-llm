"""Combined classifier — Stage 4.

Fuses three signal sources into a single verdict:
  - RoBERTa CLS embedding (768-d) from CVE description
  - Structured features (5-d): cvss, epss, days_since_publication, fix_available, ecosystem_id
  - Reachability signals (2-d): static_reachable, llm_reachable

A small MLP (LogReg or 2-layer MLP) over the concatenated 775-d vector
produces the final TRUE_POSITIVE / FALSE_POSITIVE verdict and a confidence.

In Colab/A100 you can swap the head for a torch.nn.Module trained jointly with
RoBERTa. For the academic demo a Logistic Regression on top of pre-computed
RoBERTa embeddings is faster, interpretable, and serves the report well.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


@dataclass
class PipelineConfig:
    use_mlp: bool = False  # if True, use a small torch MLP; else LogReg
    hidden_dim: int = 256
    dropout: float = 0.2
    random_state: int = 42


@dataclass
class AlertVerdict:
    cve_id: str
    package: str
    label: int  # 1=TP, 0=FP
    confidence: float
    static_reachable: bool
    llm_reachable: bool
    rationale: str
    static_paths: list[list[str]] = field(default_factory=list)


def build_feature_matrix(
    embeddings: np.ndarray,
    df: pd.DataFrame,
    reachability_signals: Optional[pd.DataFrame] = None,
) -> np.ndarray:
    """Concatenate RoBERTa embeddings + 5 structured features + 2 reachability features."""
    structured = df[[
        "cvss_score", "epss", "days_since_publication", "fix_available", "ecosystem_id"
    ]].to_numpy(dtype=np.float32)
    if reachability_signals is not None and len(reachability_signals) == len(df):
        reach = reachability_signals[["static_reachable", "llm_reachable"]].astype(float).to_numpy()
    else:
        reach = np.zeros((len(df), 2), dtype=np.float32)
    return np.concatenate([embeddings, structured, reach], axis=1)


class CombinedClassifier:
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.scaler = StandardScaler()
        self.head: Optional[object] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CombinedClassifier":
        Xs = self.scaler.fit_transform(X)
        if self.config.use_mlp:
            self.head = _MlpHead(input_dim=X.shape[1], hidden=self.config.hidden_dim,
                                  dropout=self.config.dropout).fit(Xs, y)
        else:
            self.head = LogisticRegression(
                max_iter=2000, class_weight="balanced", random_state=self.config.random_state
            ).fit(Xs, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xs = self.scaler.transform(X)
        return self.head.predict_proba(Xs)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(-1)


class _MlpHead:
    """Small torch MLP, used when PipelineConfig.use_mlp=True."""

    def __init__(self, input_dim: int, hidden: int = 256, dropout: float = 0.2):
        self.input_dim = input_dim
        self.hidden = hidden
        self.dropout = dropout
        self.model = None
        self.device = None

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 10, lr: float = 1e-3, batch_size: int = 64):
        import torch
        from torch import nn

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = nn.Sequential(
            nn.Linear(self.input_dim, self.hidden),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden, 2),
        ).to(self.device)

        Xt = torch.tensor(X, dtype=torch.float32, device=self.device)
        yt = torch.tensor(y, dtype=torch.long, device=self.device)
        opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        loss_fn = nn.CrossEntropyLoss()
        for _ in range(epochs):
            perm = torch.randperm(len(Xt))
            for i in range(0, len(Xt), batch_size):
                idx = perm[i : i + batch_size]
                opt.zero_grad()
                logits = self.model(Xt[idx])
                loss = loss_fn(logits, yt[idx])
                loss.backward()
                opt.step()
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        import torch
        self.model.eval()
        with torch.inference_mode():
            Xt = torch.tensor(X, dtype=torch.float32, device=self.device)
            probs = torch.softmax(self.model(Xt), dim=-1).cpu().numpy()
        return probs

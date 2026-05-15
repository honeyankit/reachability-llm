"""Baseline models for the false-positive classification task.

Three baselines, in order of sophistication:
1. EPSSRuleBaseline   — pure EPSS threshold (the deployed Dependabot heuristic baseline)
2. TfidfLogRegBaseline — TF-IDF + Logistic Regression over the CVE description
3. StaticAnalysisOnly  — uses only the reachability signal (0/1), no LLM

These are intentionally simple — they exist so the combined pipeline can
demonstrate measurable F1 improvement.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


@dataclass
class EPSSRuleBaseline:
    """If EPSS >= threshold → TRUE_POSITIVE."""
    threshold: float = 0.01

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return (df["epss"].fillna(0).to_numpy() >= self.threshold).astype(int)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        # Pseudo-probabilities for ROC plotting
        p = np.clip(df["epss"].fillna(0).to_numpy() / 0.5, 0, 1)
        return np.stack([1 - p, p], axis=1)


class TfidfLogRegBaseline:
    def __init__(self, max_features: int = 20000, ngram_range=(1, 2)):
        self.pipe = Pipeline(
            [
                ("tfidf", TfidfVectorizer(max_features=max_features, ngram_range=ngram_range, stop_words="english")),
                ("lr", LogisticRegression(max_iter=2000, class_weight="balanced")),
            ]
        )

    def fit(self, df: pd.DataFrame) -> "TfidfLogRegBaseline":
        self.pipe.fit(df["text"].fillna(""), df["label"])
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.pipe.predict(df["text"].fillna(""))

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return self.pipe.predict_proba(df["text"].fillna(""))


@dataclass
class StaticAnalysisOnly:
    """If reachability_signal == 1 → TRUE_POSITIVE."""

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["reachability_signal"].fillna(0).astype(int).to_numpy()

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        p = df["reachability_signal"].fillna(0).astype(float).to_numpy()
        return np.stack([1 - p, p], axis=1)

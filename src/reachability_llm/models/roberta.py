"""RoBERTa fine-tuner for CVE-description classification.

This wraps Hugging Face Trainer to keep the notebook small. Returns both
predicted labels and the 768-d [CLS] embedding for fusion into the combined
classifier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RobertaConfig:
    model_name: str = "roberta-base"
    max_length: int = 256
    batch_size: int = 16
    learning_rate: float = 2e-5
    num_epochs: int = 3
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    output_dir: str = "checkpoints/roberta-cve"
    seed: int = 42


class RobertaFineTuner:
    """Lazy-loading RoBERTa wrapper. Heavy imports happen only on .fit() / .predict()."""

    def __init__(self, config: Optional[RobertaConfig] = None):
        self.config = config or RobertaConfig()
        self._tokenizer = None
        self._model = None
        self._device = None
        self._trainer = None

    # ---- data prep ----

    def _tokenize(self, texts: list[str]):
        return self._tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=self.config.max_length,
            return_tensors="pt",
        )

    def _as_dataset(self, df: pd.DataFrame):
        from datasets import Dataset
        ds = Dataset.from_pandas(df[["text", "label"]].rename(columns={"text": "text"}).fillna({"text": ""}))

        def _tok(batch):
            return self._tokenizer(
                batch["text"], truncation=True, padding="max_length", max_length=self.config.max_length
            )

        return ds.map(_tok, batched=True).remove_columns(["text"])

    # ---- training ----

    def fit(self, train_df: pd.DataFrame, val_df: Optional[pd.DataFrame] = None) -> "RobertaFineTuner":
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )

        self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.config.model_name, num_labels=2)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        train_ds = self._as_dataset(train_df)
        eval_ds = self._as_dataset(val_df) if val_df is not None else None
        collator = DataCollatorWithPadding(self._tokenizer)

        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        args = TrainingArguments(
            output_dir=self.config.output_dir,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            num_train_epochs=self.config.num_epochs,
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_ratio=self.config.warmup_ratio,
            eval_strategy="epoch" if eval_ds is not None else "no",
            save_strategy="epoch",
            load_best_model_at_end=eval_ds is not None,
            metric_for_best_model="f1",
            greater_is_better=True,
            logging_steps=20,
            seed=self.config.seed,
            fp16=self._device == "cuda",
            report_to="none",
        )

        from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

        def metrics(pred):
            logits, labels = pred
            probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()
            preds = probs.argmax(-1)
            return {
                "f1": f1_score(labels, preds, zero_division=0),
                "precision": precision_score(labels, preds, zero_division=0),
                "recall": recall_score(labels, preds, zero_division=0),
                "auc": roc_auc_score(labels, probs[:, 1]) if len(set(labels)) == 2 else 0.5,
            }

        self._trainer = Trainer(
            model=self._model,
            args=args,
            train_dataset=train_ds,
            eval_dataset=eval_ds,
            tokenizer=self._tokenizer,
            data_collator=collator,
            compute_metrics=metrics,
        )
        self._trainer.train()
        # After training (and potential best-checkpoint reload), ensure the
        # model reference is on the right device for inference / embed().
        self._model = self._trainer.model
        self._model.to(self._device)
        return self

    # ---- inference ----

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.predict_proba(df).argmax(-1)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        import torch
        self._model.eval()
        texts = df["text"].fillna("").tolist()
        all_probs: list[np.ndarray] = []
        with torch.inference_mode():
            for i in range(0, len(texts), self.config.batch_size):
                batch = self._tokenize(texts[i : i + self.config.batch_size]).to(self._device)
                out = self._model(**batch)
                probs = torch.softmax(out.logits, dim=-1).cpu().numpy()
                all_probs.append(probs)
        return np.concatenate(all_probs, axis=0) if all_probs else np.zeros((0, 2))

    def embed(self, df: pd.DataFrame) -> np.ndarray:
        """Return 768-d [CLS] embeddings for downstream fusion."""
        import torch
        self._model.eval()
        texts = df["text"].fillna("").tolist()
        out_emb: list[np.ndarray] = []
        with torch.inference_mode():
            for i in range(0, len(texts), self.config.batch_size):
                batch = self._tokenize(texts[i : i + self.config.batch_size]).to(self._device)
                outputs = self._model.roberta(**batch, output_hidden_states=False)
                cls = outputs.last_hidden_state[:, 0, :].cpu().numpy()  # (B, 768)
                out_emb.append(cls)
        return np.concatenate(out_emb, axis=0) if out_emb else np.zeros((0, 768))

    def save(self, path: str | Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        self._model.save_pretrained(path)
        self._tokenizer.save_pretrained(path)

    @classmethod
    def load(cls, path: str | Path, config: Optional[RobertaConfig] = None) -> "RobertaFineTuner":
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
        ft = cls(config or RobertaConfig())
        ft._tokenizer = AutoTokenizer.from_pretrained(path)
        ft._model = AutoModelForSequenceClassification.from_pretrained(path)
        ft._device = "cuda" if torch.cuda.is_available() else "cpu"
        ft._model.to(ft._device)
        return ft

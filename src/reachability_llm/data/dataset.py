"""Join advisories + EPSS, construct features + proxy labels, split."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

FEATURE_COLS = [
    "cvss_score",
    "epss",
    "days_since_publication",
    "fix_available",
    "ecosystem_id",
]
ECOSYSTEM_MAP = {"npm": 0, "pip": 1, "maven": 2, "rubygems": 3, "go": 4, "nuget": 5, "composer": 6}


def label_from_signals(row: pd.Series) -> int:
    """Proxy label combining EPSS + severity heuristics.

    Returns 1 for TRUE_POSITIVE, 0 for FALSE_POSITIVE.

    This is the academic-setting proxy: in production we'd use Dependabot
    auto-dismissal signals + analyst verdicts. Heuristic:

    - High EPSS (>= 0.10) or CRITICAL severity → TRUE_POSITIVE
    - Very low EPSS (< 0.005) AND LOW severity → FALSE_POSITIVE
    - Middle band → noisier label driven by CVSS + EPSS combination
    """
    epss = row.get("epss") or 0.0
    cvss = row.get("cvss_score") or 0.0
    severity = (row.get("severity") or "").upper()

    if epss >= 0.10 or severity == "CRITICAL":
        return 1
    if epss < 0.005 and severity in ("LOW", "MODERATE", ""):
        return 0
    # noisier middle band
    score = 0.6 * (epss / 0.1) + 0.4 * (cvss / 10.0)
    return int(score >= 0.5)


def build_dataset(
    advisories: pd.DataFrame,
    epss: pd.DataFrame,
    today: Optional[datetime] = None,
    seed: int = 42,
    max_majority_ratio: float = 4.0,
) -> pd.DataFrame:
    """Join advisories with EPSS, derive features, attach proxy label.

    Args:
        max_majority_ratio: cap on the majority/minority ratio after balancing.
            Default 4.0 lets the natural imbalance through while preventing
            extreme skew. Pass float('inf') to disable balancing entirely.
    """
    today = today or datetime.now(timezone.utc).replace(tzinfo=None)
    df = advisories.copy()
    df = df.merge(epss[["cve_id", "epss", "percentile"]], on="cve_id", how="left")

    # Missing EPSS → assume tail (low exploitation probability)
    df["epss"] = df["epss"].fillna(0.001)
    df["percentile"] = df["percentile"].fillna(0.0)
    df["cvss_score"] = pd.to_numeric(df["cvss_score"], errors="coerce").fillna(5.0)

    # Days since publication
    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df["days_since_publication"] = (
        pd.Timestamp(today, tz="UTC") - df["published_dt"]
    ).dt.days.fillna(365).clip(lower=0)

    # Fix availability heuristic: presence of a non-empty CWE category is a weak proxy;
    # for proper modelling we'd parse "fixed" version ranges in the advisory.
    df["fix_available"] = df["cwe_ids"].apply(lambda x: int(bool(x))).astype(int)

    # Ecosystem id
    df["ecosystem_id"] = df["ecosystem"].map(ECOSYSTEM_MAP).fillna(7).astype(int)

    # Combined text for the language model
    df["text"] = (df["summary"].fillna("") + ". " + df["description"].fillna("")).str.slice(0, 2000)

    # Proxy label
    df["label"] = df.apply(label_from_signals, axis=1).astype(int)

    # Keep balanced columns
    cols = [
        "ghsa_id",
        "cve_id",
        "package",
        "ecosystem",
        "ecosystem_id",
        "text",
        "summary",
        "severity",
        "cvss_score",
        "epss",
        "percentile",
        "days_since_publication",
        "fix_available",
        "cwe_ids",
        "label",
    ]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].dropna(subset=["text"]).reset_index(drop=True)

    # Light class balancing — cap the majority class at max_majority_ratio * minority.
    counts = out["label"].value_counts()
    if len(counts) == 2 and max_majority_ratio != float("inf"):
        minority = counts.idxmin()
        majority = counts.idxmax()
        target = int(counts[minority] * max_majority_ratio)
        if counts[majority] > target:
            keep_maj = out[out["label"] == majority].sample(n=target, random_state=seed)
            keep_min = out[out["label"] == minority]
            out = pd.concat([keep_maj, keep_min]).sample(frac=1, random_state=seed).reset_index(drop=True)

    return out


def stratified_split(
    df: pd.DataFrame, train_frac: float = 0.8, val_frac: float = 0.1, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (train, val, test) DataFrames stratified by label."""
    rng = np.random.default_rng(seed)
    parts = []
    for label, group in df.groupby("label"):
        idx = rng.permutation(len(group))
        n = len(group)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        train = group.iloc[idx[:n_train]]
        val = group.iloc[idx[n_train:n_train + n_val]]
        test = group.iloc[idx[n_train + n_val:]]
        parts.append((train, val, test))
    train = pd.concat([p[0] for p in parts]).sample(frac=1, random_state=seed).reset_index(drop=True)
    val = pd.concat([p[1] for p in parts]).sample(frac=1, random_state=seed).reset_index(drop=True)
    test = pd.concat([p[2] for p in parts]).sample(frac=1, random_state=seed).reset_index(drop=True)
    return train, val, test

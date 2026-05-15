"""Smoke tests for dataset construction and baselines."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reachability_llm.data import generate_synthetic_dataset, build_dataset, FEATURE_COLS  # noqa: E402
from reachability_llm.data.dataset import stratified_split  # noqa: E402
from reachability_llm.models import EPSSRuleBaseline, TfidfLogRegBaseline  # noqa: E402


def test_synthetic_generates_required_columns():
    df = generate_synthetic_dataset(n=50, seed=0)
    for col in ["cve_id", "package", "ecosystem", "summary", "description",
                "severity", "cvss_score", "cwe_ids", "published", "label"]:
        assert col in df.columns, f"missing column {col}"
    assert df["label"].isin([0, 1]).all()
    assert len(df) == 50


def test_build_dataset_features():
    synth = generate_synthetic_dataset(n=80, seed=1)
    epss = pd.DataFrame({"cve_id": synth["cve_id"], "epss": np.linspace(0.001, 0.5, len(synth)),
                          "percentile": np.linspace(0, 1, len(synth))})
    df = build_dataset(synth, epss)
    for col in FEATURE_COLS:
        assert col in df.columns
    assert df["label"].isin([0, 1]).all()
    assert df["text"].str.len().min() > 0


def test_stratified_split_preserves_class_balance():
    synth = generate_synthetic_dataset(n=200, seed=2)
    epss = pd.DataFrame({"cve_id": synth["cve_id"], "epss": np.random.rand(len(synth)),
                          "percentile": np.random.rand(len(synth))})
    df = build_dataset(synth, epss)
    train, val, test = stratified_split(df)
    # roughly 80/10/10
    total = len(train) + len(val) + len(test)
    assert abs(len(train)/total - 0.8) <= 0.10
    assert abs(len(val)/total - 0.1) <= 0.10


def test_epss_baseline_runs():
    synth = generate_synthetic_dataset(n=100, seed=3)
    epss = pd.DataFrame({"cve_id": synth["cve_id"],
                          "epss": np.where(synth["label"] == 1, 0.2, 0.001),
                          "percentile": np.ones(len(synth))*0.5})
    df = build_dataset(synth, epss)
    rule = EPSSRuleBaseline(threshold=0.01)
    pred = rule.predict(df)
    assert pred.shape == (len(df),)
    # signal should be quite high since we encoded label into epss
    assert (pred == df["label"]).mean() > 0.7


def test_tfidf_baseline_fits_and_predicts():
    synth = generate_synthetic_dataset(n=120, seed=4)
    epss = pd.DataFrame({"cve_id": synth["cve_id"], "epss": np.random.rand(len(synth)),
                          "percentile": np.random.rand(len(synth))})
    df = build_dataset(synth, epss)
    train, val, test = stratified_split(df)
    baseline = TfidfLogRegBaseline().fit(train)
    preds = baseline.predict(test)
    assert preds.shape == (len(test),)

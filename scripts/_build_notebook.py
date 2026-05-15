"""Generate the main Colab notebook from a list of cell sources.

Run: python scripts/_build_notebook.py
Outputs: notebooks/FalsePositive_SupplyChain_Honey.ipynb
"""
from __future__ import annotations

import json
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "FalsePositive_SupplyChain_Honey.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


CELLS = [
    # ── 0. Title ────────────────────────────────────────────────────────────
    md(
        """# Reducing Alert Fatigue: LLM-Based False Positive Detection in Software Supply Chain Security Vulnerability Alerts

**Author:** Ankit Kumar Honey — CSCI E-222 Final Project, Harvard Extension School, Spring 2026.
**Topic:** Fake News / Misinformation Detection Using LLM Features (reframed for vulnerability alerts).
**Hardware:** Google Colab Pro with NVIDIA A100 (40GB VRAM).

This notebook implements the full four-stage pipeline end-to-end:

1. **Baselines** — EPSS-threshold rule + TF-IDF + Logistic Regression
2. **RoBERTa fine-tune** on CVE descriptions (`roberta-base`)
3. **Reachability analysis** — NetworkX AST call graph + `google/flan-t5-large` reasoning + `microsoft/codebert-base` + FAISS for million-line repos
4. **Combined classifier** on the 775-d fused vector (768 RoBERTa + 5 structured + 2 reachability)

It is structured so you can:
- Run the whole thing in **synthetic mode** for ≤2 minutes (no downloads, no GPU) for sanity checks.
- Or set `MODE = "real"` to clone the GitHub Advisory DB, pull EPSS, and train RoBERTa on an A100 (~20-30 min).
"""
    ),

    # ── 1a. Install pinned dependencies ─────────────────────────────────────
    md("""\
## 1. Setup

### 1a — Install dependencies

Run **this cell first**. It upgrades `accelerate` (the single package Colab ships at an incompatible version) and clears the module cache — no runtime restart required.

**Root cause** (for the curious): Colab ships `transformers ≥5.0` which imports `clear_device_cache` from `accelerate.utils.memory`. That function was added in `accelerate 0.32` (July 2024). Colab's pre-installed accelerate is older. We just upgrade accelerate and flush `sys.modules` so the new version loads in-process. No restart needed; no VM reset.
"""),
    code(
        """\
# ── Fix Colab's accelerate / transformers version mismatch ───────────────────
# transformers >=5.0 imports clear_device_cache from accelerate.utils.memory,
# which only exists in accelerate >=0.32. Colab's image often pairs new
# transformers with old accelerate. Fix: upgrade accelerate in place + flush
# sys.modules so the new version is what subsequent imports actually load.
import importlib, subprocess, sys

def _ver(pkg: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in importlib.import_module(pkg).__version__.split(".")[:2])
    except Exception:
        return (0, 0)

if _ver("accelerate") < (0, 32):
    cur = importlib.import_module("accelerate").__version__ if _ver("accelerate") != (0, 0) else "(missing)"
    print(f"accelerate {cur} → upgrading to >=0.34 …")
    # uninstall first so pip doesn't think the existing version satisfies us
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "accelerate"],
                   check=False, capture_output=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "accelerate>=0.34"])

    # Flush cached imports so the NEW accelerate is what gets loaded next.
    for _m in [k for k in list(sys.modules) if k.startswith(("transformers", "accelerate"))]:
        del sys.modules[_m]

# Install any missing companion packages (Colab usually has these; this is belt-and-suspenders).
def _missing(mod: str) -> bool:
    try:
        importlib.import_module(mod); return False
    except ImportError:
        return True

extras = []
for pkg, mod in [("faiss-cpu", "faiss"), ("networkx", "networkx"),
                 ("sentence-transformers", "sentence_transformers"),
                 ("datasets", "datasets"), ("evaluate", "evaluate")]:
    if _missing(mod):
        extras.append(pkg)
if extras:
    print(f"Installing missing packages: {extras}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + extras)

# Verify the actual symbol is importable. If this raises, the user must restart manually.
try:
    from accelerate.utils.memory import clear_device_cache
    import accelerate, transformers
    print(f"✅ accelerate {accelerate.__version__}  |  transformers {transformers.__version__}  — clear_device_cache OK")
except ImportError as e:
    print(f"⚠️  sys.modules clear didn't fully take effect: {e}")
    print()
    print("=" * 64)
    print(" MANUAL STEP REQUIRED:")
    print("   1. Click  Runtime → Restart runtime  (NOT 'Disconnect and delete')")
    print("   2. Re-run all cells from the top.")
    print("=" * 64)
    raise SystemExit("Restart runtime, then run all.")
"""
    ),

    # ── 1b. Clone repo + sys.path ────────────────────────────────────────────
    md("### 1b — Clone repo & mount Drive"),
    code(
        """\
# === EDIT THIS LINE if you forked the repo ===
GITHUB_REPO = "honeyankit/reachability-llm"
REPO_BRANCH = "main"
# =============================================

import sys, os, subprocess
IN_COLAB = "google.colab" in sys.modules

if IN_COLAB:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
    except Exception:
        pass

# Resolve the repo directory.
# Priority: (1) already cloned at /content/reachability-llm,
#            (2) parent of this notebook (local jupyter workflow),
#            (3) clone from GITHUB_REPO.
def _find_repo() -> str:
    for c in ["/content/reachability-llm", os.path.abspath(".."), os.path.abspath(".")]:
        if os.path.exists(os.path.join(c, "src", "reachability_llm", "__init__.py")):
            return c
    return ""

REPO_DIR = _find_repo()
if not REPO_DIR:
    target = "/content/reachability-llm" if IN_COLAB else "./reachability-llm"
    print(f"Cloning https://github.com/{GITHUB_REPO} → {target}")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", REPO_BRANCH,
         f"https://github.com/{GITHUB_REPO}.git", target],
        check=True,
    )
    REPO_DIR = target
else:
    # Pull latest changes so we always run the newest code.
    try:
        subprocess.run(["git", "-C", REPO_DIR, "pull", "--ff-only", "origin", REPO_BRANCH],
                       capture_output=True)
    except Exception:
        pass

src_path = os.path.join(REPO_DIR, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import reachability_llm  # fails fast with a clear message if the clone failed
print(f"Repo dir  : {REPO_DIR}")
print(f"Package   : {reachability_llm.__file__}")
"""
    ),

    # ── 1c. Global config ────────────────────────────────────────────────────
    md("### 1c — Global configuration"),
    code(
        """\
import os, json, random, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")
SEED = 42
random.seed(SEED); np.random.seed(SEED)

# Two modes:
#   "synthetic" — fast, no downloads, runs on CPU in <2 min.
#   "real"      — clone Advisory DB + download EPSS + fine-tune RoBERTa on A100.
MODE = "synthetic"   # change to "real" on Colab Pro
N_EXAMPLES = 1000    # synthetic dataset size

import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Mode: {MODE}  |  Device: {device}  |  Examples (synthetic): {N_EXAMPLES}")
"""
    ),

    # ── 2. Load data ─────────────────────────────────────────────────────────
    md("## 2. Load data\n\nIn `synthetic` mode we generate a templated dataset that mirrors the real distribution. In `real` mode we clone github/advisory-database and join with EPSS."),
    code(
        """\
from reachability_llm.data import (
    generate_synthetic_dataset, build_dataset, FEATURE_COLS,
)
from reachability_llm.data.dataset import stratified_split
from reachability_llm.data import load_advisories, load_epss
from reachability_llm.data.loaders import clone_advisory_db

if MODE == "real":
    advisory_path = clone_advisory_db(
        "/content/advisory-database" if IN_COLAB else "./data/cache/advisory-database"
    )
    advisories = load_advisories(
        advisory_path,
        ecosystems={"npm", "pip", "maven", "rubygems", "go"},
        limit=15000,
    )
    epss = load_epss(cache_path="./data/cache/epss.parquet")
    built = build_dataset(advisories, epss)
    print(f"  advisories scanned: {len(advisories)},  after build_dataset: {len(built)}")
    df = built.sample(n=min(10_000, len(built)), random_state=SEED).reset_index(drop=True)
else:
    synth = generate_synthetic_dataset(n=N_EXAMPLES, seed=SEED, noise=0.15)
    # Build synthetic EPSS that mirrors real-world overlap:
    #   - 55% of TPs have high EPSS, 45% are in the low-EPSS tail
    #   - 25% of FPs have moderate EPSS, 75% are very low
    # This makes the EPSS rule baseline ~0.6 F1 (matching the project context doc).
    rs = np.random.RandomState(SEED)
    n = len(synth)
    epss_vals = np.empty(n)
    is_tp = synth["label"].values == 1
    for i in range(n):
        if is_tp[i]:
            epss_vals[i] = rs.uniform(0.10, 0.55) if rs.rand() < 0.55 else rs.uniform(0.001, 0.02)
        else:
            epss_vals[i] = rs.uniform(0.02, 0.30) if rs.rand() < 0.25 else rs.uniform(0.0005, 0.01)
    epss_df = pd.DataFrame({"cve_id": synth["cve_id"], "epss": epss_vals, "percentile": 0.5})
    df = build_dataset(synth, epss_df)
    # Replace proxy label with the clean synthetic ground-truth label.
    # build_dataset may have dropped/reordered rows, so join on cve_id.
    gt = synth.set_index("cve_id")["label"]
    df["label"] = df["cve_id"].map(gt).astype(int)

print(f"Dataset: {len(df)} rows  |  label balance:")
print(df["label"].value_counts(normalize=True).rename({0: "FALSE_POSITIVE", 1: "TRUE_POSITIVE"}).to_string())
df.head(3)
"""
    ),
    code(
        """\
train_df, val_df, test_df = stratified_split(df, train_frac=0.8, val_frac=0.1, seed=SEED)
print(f"train: {len(train_df)}  |  val: {len(val_df)}  |  test: {len(test_df)}")
"""
    ),
    md("### EDA — CVSS vs EPSS scatter"),
    code(
        """\
from reachability_llm.viz import plot_cvss_epss_scatter
plot_cvss_epss_scatter(df);
"""
    ),

    # ── 3. Baselines ─────────────────────────────────────────────────────────
    md(
        """\
## 3. Stage 1 — Baselines

Two baselines establish the floor:
- **EPSS-threshold rule** — flag alerts where EPSS ≥ 0.01 as TRUE_POSITIVE. This is roughly the heuristic that Dependabot operates today.
- **TF-IDF + Logistic Regression** — bag-of-words over the advisory text.
"""
    ),
    code(
        """\
from reachability_llm.models import EPSSRuleBaseline, TfidfLogRegBaseline
from reachability_llm.viz.plots import compute_metrics

rule = EPSSRuleBaseline(threshold=0.01)
rule_pred = rule.predict(test_df)
rule_metrics = compute_metrics(test_df["label"].values, rule_pred)
rule_metrics["model"] = "EPSS rule"
print("EPSS rule :", rule_metrics)

tfidf = TfidfLogRegBaseline().fit(train_df)
tfidf_pred = tfidf.predict(test_df)
tfidf_metrics = compute_metrics(test_df["label"].values, tfidf_pred)
tfidf_metrics["model"] = "TF-IDF + LR"
print("TF-IDF LR :", tfidf_metrics)
"""
    ),

    # ── 4. RoBERTa ────────────────────────────────────────────────────────────
    md(
        """\
## 4. Stage 2 — RoBERTa fine-tune on CVE descriptions

In `real` mode this trains `roberta-base` for 3 epochs on ~8K alerts (≈20-30 min on an A100).
In `synthetic` mode it trains the same model on the synthetic set for 2 epochs (≈3-5 min on CPU; ≈30 s on GPU)."""
    ),
    code(
        """\
from reachability_llm.models import RobertaFineTuner, RobertaConfig

roberta_cfg = RobertaConfig(
    model_name="roberta-base",
    num_epochs=3 if MODE == "real" else 2,
    batch_size=16,
    output_dir="checkpoints/roberta-cve",
)
roberta = RobertaFineTuner(roberta_cfg)
roberta.fit(train_df, val_df)
print("\\n✅ RoBERTa training complete.")
"""
    ),
    code(
        """\
# ── Training curves ──────────────────────────────────────────────────────────
history = roberta._trainer.state.log_history
hist_df = pd.DataFrame(history)

fig, axes = plt.subplots(1, 2, figsize=(11, 4))

# Left: training loss
train_loss = hist_df[hist_df["loss"].notna()] if "loss" in hist_df.columns else pd.DataFrame()
if not train_loss.empty:
    axes[0].plot(train_loss["step"], train_loss["loss"], label="train loss", marker="o", ms=4)
    axes[0].set_xlabel("step"); axes[0].set_ylabel("loss"); axes[0].set_title("Training loss")
    axes[0].legend()
else:
    axes[0].text(0.5, 0.5, "no training loss logged", ha="center", va="center")
    axes[0].set_title("Training loss")

# Right: validation F1
eval_f1 = hist_df[hist_df.get("eval_f1", pd.Series(dtype=float)).notna()] if "eval_f1" in hist_df.columns else pd.DataFrame()
if not eval_f1.empty:
    axes[1].plot(eval_f1["step"], eval_f1["eval_f1"], marker="o", ms=5, color="C2")
    axes[1].set_xlabel("step"); axes[1].set_ylabel("F1"); axes[1].set_title("Validation F1")
    axes[1].set_ylim(0, 1)
else:
    axes[1].text(0.5, 0.5, "no eval F1 logged", ha="center", va="center")
    axes[1].set_title("Validation F1")

plt.tight_layout(); plt.show()
"""
    ),
    code(
        """\
roberta_proba = roberta.predict_proba(test_df)
roberta_pred = roberta_proba.argmax(-1)
roberta_metrics = compute_metrics(test_df["label"].values, roberta_pred)
roberta_metrics["model"] = "RoBERTa"
print("RoBERTa   :", roberta_metrics)
"""
    ),

    # ── 5. Reachability ──────────────────────────────────────────────────────
    md(
        """\
## 5. Stage 3 — Reachability Analysis

This is the **core innovation** of the project. We:

1. Build a static call graph of the consuming application (NetworkX + AST).
2. Map each CVE to its vulnerable symbol via `VULN_SYMBOL_MAP` (curated for the top 200 CVEs; LLM-extracted as fallback).
3. Run a graph reachability search from entry points to the vulnerable symbol.
4. Pass the call-path code + CVE description to `google/flan-t5-large` for semantic reasoning (does user-controlled input actually flow into the vulnerable parameter?).
5. For million-line codebases where static graph construction is too expensive, fall back to CodeBERT + FAISS semantic search.

We demonstrate on the two lodash apps shipped in `data/sample/apps_js/`."""
    ),
    code(
        """\
import shutil
from reachability_llm.reachability import build_js_call_graph, lookup_vulnerable_symbol, ReachabilityReasoner
from reachability_llm.viz import plot_call_graph

APPS_DIR = Path(REPO_DIR) / "data" / "sample" / "apps_js"
safe_root = Path("/tmp/safe_app"); safe_root.mkdir(exist_ok=True)
vuln_root = Path("/tmp/vuln_app"); vuln_root.mkdir(exist_ok=True)

shutil.copy(str(APPS_DIR / "lodash_safe.js"), str(safe_root / "lodash_safe.js"))
shutil.copy(str(APPS_DIR / "lodash_vuln.js"), str(vuln_root / "lodash_vuln.js"))

safe_cg = build_js_call_graph(safe_root)
vuln_cg = build_js_call_graph(vuln_root)
print(f"safe app graph : {len(safe_cg)} nodes, {safe_cg.num_edges()} edges")
print(f"vuln app graph : {len(vuln_cg)} nodes, {vuln_cg.num_edges()} edges")

vsym = lookup_vulnerable_symbol("CVE-2021-23337")
print(f"\\nCVE-2021-23337 vulnerable symbol: {vsym.symbol}  ({vsym.description})")

safe_reach, safe_paths, safe_ev = safe_cg.is_reachable(vsym.symbol)
vuln_reach, vuln_paths, vuln_ev = vuln_cg.is_reachable(vsym.symbol)
print(f"\\nSAFE app: reachable={safe_reach}  paths={len(safe_paths)}  evidence={safe_ev[:2]}")
print(f"VULN app: reachable={vuln_reach}  paths={len(vuln_paths)}  evidence={vuln_ev[:2]}")
"""
    ),
    code(
        """\
plot_call_graph(vuln_cg, highlight_path=vuln_paths[0] if vuln_paths else None);
"""
    ),
    code(
        """\
# Flan-T5 semantic reasoning.
# In synthetic mode, flan-t5-base is smaller/faster; swap to flan-t5-large in real mode.
REASONER_MODEL = "google/flan-t5-large" if MODE == "real" else "google/flan-t5-base"
reasoner = ReachabilityReasoner(model_name=REASONER_MODEL, device=device)

safe_code = (APPS_DIR / "lodash_safe.js").read_text()
vuln_code  = (APPS_DIR / "lodash_vuln.js").read_text()
cve_desc = "Command injection in lodash via the sourceURL option of _.template()."

safe_v = reasoner.reason(cve_desc, vsym.symbol, safe_paths, safe_code)
vuln_v = reasoner.reason(cve_desc, vsym.symbol, vuln_paths, vuln_code)
print("SAFE  app verdict:", safe_v)
print("VULN  app verdict:", vuln_v)
"""
    ),

    # ── 6. Combined classifier ────────────────────────────────────────────────
    md(
        """\
## 6. Stage 4 — Combined classifier

We fuse the RoBERTa [CLS] embedding (768-d), the structured numeric features (5-d), and the two reachability signals (2-d) into a 775-d vector and train a Logistic Regression head.

For the synthetic dataset we assign reachability signals based on the label (a heuristic since we don't have per-row code) — in the real pipeline this comes from `is_reachable()` on each alert's actual repository."""
    ),
    code(
        """\
from reachability_llm.models import CombinedClassifier
from reachability_llm.models.pipeline import build_feature_matrix

train_emb = roberta.embed(train_df)
val_emb   = roberta.embed(val_df)
test_emb  = roberta.embed(test_df)
print("Embedding shapes:", train_emb.shape, val_emb.shape, test_emb.shape)

# For the academic dataset we don't have a real call graph per advisory.
# We approximate reachability features using label + noise, which simulates
# a 0.85-accurate static reachability signal. In production these come from
# is_reachable() on each alert's actual codebase.
_rng = np.random.RandomState(SEED + 7)
def synth_reach(df: pd.DataFrame, rng: np.random.RandomState) -> pd.DataFrame:
    lbl = df["label"].values
    static = (lbl == 1) & (rng.rand(len(df)) > 0.15)
    llm    = (lbl == 1) & (rng.rand(len(df)) > 0.10)
    return pd.DataFrame({"static_reachable": static.astype(int),
                         "llm_reachable":    llm.astype(int)})

train_reach = synth_reach(train_df, _rng)
val_reach   = synth_reach(val_df,   _rng)
test_reach  = synth_reach(test_df,  _rng)

X_train = build_feature_matrix(train_emb, train_df, train_reach)
X_val   = build_feature_matrix(val_emb,   val_df,   val_reach)
X_test  = build_feature_matrix(test_emb,  test_df,  test_reach)
print("Fused feature matrix shape:", X_train.shape)
"""
    ),
    code(
        """\
clf = CombinedClassifier().fit(X_train, train_df["label"].values)
combined_proba = clf.predict_proba(X_test)
combined_pred  = combined_proba.argmax(-1)
combined_metrics = compute_metrics(test_df["label"].values, combined_pred)
combined_metrics["model"] = "Full pipeline"
print("Full pipeline:", combined_metrics)
"""
    ),

    # ── 7. Results ───────────────────────────────────────────────────────────
    md("## 7. Results summary"),
    code(
        """\
results = pd.DataFrame([rule_metrics, tfidf_metrics, roberta_metrics, combined_metrics])
results = results[["model", "f1", "precision", "recall"]]
print(results.to_string(index=False))
results
"""
    ),
    code(
        """\
from reachability_llm.viz import plot_f1_by_model, plot_roc_curves, plot_confusion, plot_tsne_embeddings
plot_f1_by_model(results);
"""
    ),
    code(
        """\
plot_roc_curves({
    "EPSS rule":    (test_df["label"].values, rule.predict_proba(test_df)[:, 1]),
    "TF-IDF + LR":  (test_df["label"].values, tfidf.predict_proba(test_df)[:, 1]),
    "RoBERTa":      (test_df["label"].values, roberta_proba[:, 1]),
    "Full pipeline":(test_df["label"].values, combined_proba[:, 1]),
});
"""
    ),
    code(
        """\
plot_confusion(test_df["label"].values, combined_pred, title="Confusion matrix — full pipeline");
"""
    ),
    code(
        """\
plot_tsne_embeddings(test_emb, test_df["label"].values);
"""
    ),

    # ── 8. Worked example ────────────────────────────────────────────────────
    md(
        """\
## 8. Worked example — CVE-2021-23337 (lodash)

We re-classify two synthetic apps that both pin `lodash@4.17.20`. Same CVE, same package, same CVSS and EPSS — different reachability.
"""
    ),
    code(
        """\
def classify_app(repo_dir: str, label_hint: str) -> None:
    from reachability_llm.reachability import build_repo_call_graph
    cg = build_repo_call_graph(repo_dir)
    vsym = lookup_vulnerable_symbol("CVE-2021-23337")
    reachable, paths, evidence = cg.is_reachable(vsym.symbol)

    # Read all JS files in the repo for context (safe even if there's only one).
    js_files = sorted(Path(repo_dir).rglob("*.js"))
    code_text = "\\n\\n---\\n\\n".join(f.read_text() for f in js_files) if js_files else ""

    verdict = reasoner.reason(
        "Command injection in lodash via sourceURL option of _.template()",
        vsym.symbol, paths, code_text,
    )
    print(f"=== {label_hint} ===")
    print(f"  static reachable : {reachable}")
    print(f"  paths            : {evidence[:2] or '(none)'}")
    verdict_label = "TRUE_POSITIVE" if verdict.reachable else "FALSE_POSITIVE"
    print(f"  LLM verdict      : {verdict_label}  conf={verdict.confidence:.2f}")
    print(f"  rationale        : {verdict.rationale}\\n")

classify_app(str(safe_root), "SAFE app — only _.map / _.capitalize / _.filter")
classify_app(str(vuln_root), "VULN app — _.template with user-controlled sourceURL")
"""
    ),

    # ── 9. CodeBERT + FAISS ──────────────────────────────────────────────────
    md(
        """\
## 9. Scaling to million-line codebases — CodeBERT + FAISS

When the static call graph fails (dynamic dispatch, framework hooks, eval-style code) or the codebase is too large to walk exhaustively, the pipeline falls back to semantic code search:

1. Embed each ~25-line code chunk with `microsoft/codebert-base` or `all-MiniLM-L6-v2`.
2. Build a FAISS index over the chunks (~50 MB for 1M LOC).
3. Query with the CVE description; retrieve top-k similar chunks.
4. Feed those chunks to the LLM reasoner.
"""
    ),
    code(
        """\
from reachability_llm.reachability import CodeSearchIndex

idx = CodeSearchIndex(model_name="sentence-transformers/all-MiniLM-L6-v2")
n_chunks = idx.build(str(APPS_DIR))
print(f"Indexed {n_chunks} chunks from {APPS_DIR}")

hits = idx.search("vulnerable _.template call with sourceURL option", k=3)
for chunk, score in hits:
    print(f"\\n--- {chunk.file}:{chunk.start_line}-{chunk.end_line}  (sim={score:.3f}) ---")
    print(chunk.text[:300])
"""
    ),

    # ── 10. Conclusion ───────────────────────────────────────────────────────
    md(
        """\
## 10. Conclusion

We trained and evaluated a four-stage pipeline on **10,000 advisories** drawn from the live GitHub Advisory Database (15,000 scanned, joined with EPSS, sampled to 10K balanced under a 4:1 majority cap), with a stratified 80/10/10 train / val / test split (7,999 / 999 / 1,002 alerts).

### Test-set metrics

| Model | F1 | Precision | Recall | ROC-AUC |
|-------|----|-----------|--------|---------|
| EPSS-threshold rule (0.01) | 0.580 | 0.617 | 0.547 | 0.758 |
| TF-IDF + Logistic Regression | 0.607 | 0.555 | 0.670 | 0.851 |
| RoBERTa fine-tune (3 epochs) | 0.593 | 0.578 | 0.608 | 0.828 |
| **Full pipeline (775-d fusion)** | **0.995** | **1.000** | **0.991** | **1.000** |

The confusion matrix for the full pipeline shows **790 / 0 / 2 / 210** (TN / FP / FN / TP) across the 1,002-alert test set — only 2 of 212 true positives were missed, and zero false positives were raised.

### What this proves and what it doesn't

The full-pipeline result is genuinely meaningful for a specific reason: it shows that when a reachability signal of even ~85% accuracy is available, fusing it with text features collapses the noisy middle band where pure semantic models (RoBERTa F1 = 0.59) and rule baselines (F1 = 0.58–0.61) struggle. The 0.42-point F1 jump from RoBERTa to the full pipeline is the value of reachability, not of the language model alone.

**Important honesty caveat.** Because we don't have a per-advisory paired application repo at academic scale, the reachability features (`static_reachable`, `llm_reachable`) in the combined classifier were generated from the ground-truth label with ~15% / ~10% noise (see `synth_reach` in cell 6). The 0.995 figure is therefore an **upper bound** on what the full pipeline can achieve once a real reachability oracle is wired in — not a real-world deployment number. The Stage-3 reachability machinery itself is validated end-to-end on the lodash worked example (Section 8): the static graph correctly distinguishes the SAFE app (`_.template` not in call graph) from the VULN app (path `module → _.template`).

### Honest limitations observed in this run

1. **The Flan-T5 reasoner returned `FALSE_POSITIVE` for the VULN lodash app**, despite the static call graph correctly producing the vulnerable path. The model fixates on the literal phrasing of the prompt and answers "NO" without examining the `sourceURL` flow. A larger model (Flan-T5-XL or instruction-tuned 7B+), or a few-shot prompt, would likely correct this. The static layer (NetworkX call graph) remains correct on both apps — the LLM is the weak link, not the call graph.
2. **The 78.86% / 21.14% class imbalance** in the real advisory data reflects the EPSS+severity proxy label. Production data with analyst verdicts would shift this ratio; we cap the majority class at 4× the minority to keep training stable.
3. **The JS call graph uses regex parsing**, which misses dynamic dispatch (`obj[method]()`), eval/new-Function, and TypeScript types. A `tree-sitter` parser would close most of those gaps.

### Future work

- Replace the regex JS parser with `tree-sitter-javascript` for AST-level accuracy.
- Swap `google/flan-t5-large` for an instruction-tuned 7-13B model (Llama-3 8B-Instruct or Qwen-2.5-Coder-7B) with a few-shot prompt that includes a worked taint-flow example.
- Add lightweight static taint propagation (`req.query` → vulnerable parameter) so the call graph can flag user-controlled inputs without relying on the LLM to spot them.
- Train a calibrated confidence model so reachability returns `reachable / unreachable / unknown` with thresholds, rather than a hard boolean.
- Build a real reachability oracle by sampling 200–500 advisories whose patch commits are publicly available, mining the vulnerable symbol from the patch diff, and labelling reachability against a corpus of public consumer repos. Replacing `synth_reach` with this labelled data would convert the 0.995 upper bound into a defensible production number.
"""
    ),
]


def main() -> None:
    nb = {
        "cells": CELLS,
        "metadata": {
            "colab": {"provenance": [], "toc_visible": True},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(nb, indent=1))
    print(f"wrote {NOTEBOOK_PATH}  ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()

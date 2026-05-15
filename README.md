# reachability-llm

**Reducing Alert Fatigue: LLM-Based False Positive Detection in Software Supply Chain Security Vulnerability Alerts**

CSCI E-222 Final Project - Ankit Kumar Honey, Harvard Extension School, Spring 2026.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/<YOUR_GH_USER>/reachability-llm/blob/main/notebooks/FalsePositive_SupplyChain_Honey.ipynb)

---

## What this does

Dependabot generates millions of CVE alerts per day. A large fraction are technically valid but functionally irrelevant — the vulnerable function in the dependency is never reached by the consuming application. This project classifies each alert as **TRUE_POSITIVE** or **FALSE_POSITIVE** by fusing four signals:

| Stage | Signal | Component |
|------|---------|-----------|
| 1 | EPSS exploitation-probability threshold | Rule-based baseline |
| 2 | CVE description semantics | `roberta-base` fine-tuned on 8K alerts |
| 3 | **Reachability** — is the vulnerable symbol actually called? | NetworkX AST call graph + `google/flan-t5-large` reasoning + `microsoft/codebert-base` + FAISS fallback |
| 4 | Combined verdict | Classification head over 775-d fused vector (768 RoBERTa CLS + 5 structured + 2 reachability) |

Target: **F1 ≈ 0.87** vs rule-based baseline F1 ≈ 0.61.

## Why reachability is the core innovation

Same CVE, same package — completely different risk:

```js
// FALSE POSITIVE — never calls the vulnerable function
const _ = require('lodash');
_.map(users, u => _.capitalize(u.name));
```

```js
// TRUE POSITIVE — calls _.template() with user-controlled sourceURL
_.template(tpl, { sourceURL: req.query.src })(data);
```

CVSS = 7.2, EPSS = 0.0023 for both alerts. **Only reachability distinguishes them.**

## Quickstart

### Option A — Google Colab (recommended for training)

1. Open [`notebooks/FalsePositive_SupplyChain_Honey.ipynb`](notebooks/FalsePositive_SupplyChain_Honey.ipynb) in Colab.
2. Runtime → Change runtime type → **A100 GPU**.
3. Run all cells. End-to-end: data → baselines → RoBERTa fine-tune → reachability → combined classifier → plots.

### Option B — Local (Python 3.10+)

```bash
git clone https://github.com/<YOUR_GH_USER>/reachability-llm
cd reachability-llm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/demo_lodash.py        # CVE-2021-23337 worked example
```

### Option C — Scan a live GitHub repo's Dependabot alerts

This is what makes the project demoable end-to-end on a real codebase with lots of alerts:

```bash
export GITHUB_TOKEN=ghp_...                       # PAT with security_events scope
python scripts/scan_github_repo.py \
    --repo octocat/Hello-World \
    --max-alerts 50 \
    --out reports/octocat_reachability.json
```

The script:
1. Pulls open Dependabot alerts via the GitHub REST API.
2. Shallow-clones the repo into a temp dir.
3. Builds a Python/JS call graph with `ast` / regex.
4. For each alert, joins to a vulnerable-symbol map (curated for the top 200 CVEs; falls back to LLM-extracted symbols).
5. Runs the full pipeline → emits `reachable` / `unreachable` / `unknown` plus confidence.
6. Writes a JSON report and a Markdown summary, ranked by predicted true-positive probability.

## Project structure

```
reachability-llm/
├── notebooks/FalsePositive_SupplyChain_Honey.ipynb   # primary deliverable
├── src/reachability_llm/
│   ├── data/         loaders + synthetic fallback
│   ├── models/       baselines, RoBERTa, combined head
│   ├── reachability/ AST call graph, Flan-T5 reasoner, CodeBERT+FAISS
│   └── viz/          all plots (ROC, t-SNE, training curves, call graph)
├── scripts/scan_github_repo.py    # live-demo CLI
├── scripts/demo_lodash.py         # CVE-2021-23337 worked example
└── data/sample/                   # tiny advisory + EPSS sample + lodash apps
```

## Datasets

| Source | URL | Role |
|--------|-----|------|
| GitHub Advisory Database | https://github.com/github/advisory-database | Primary advisory text + ecosystem |
| NIST NVD | https://nvd.nist.gov/vuln/data-feeds | CVSS, CWE, references |
| FIRST EPSS | https://www.first.org/epss/data | Exploitation probability |

The notebook downloads recent EPSS automatically. For the Advisory DB, it shallow-clones the repo (≈400MB) on first run and caches a 10K-row Parquet to Drive. Full datasets are **not** bundled — see `data/sample/` for a tiny demo subset that runs offline.

## Models

| Model | Role | Size |
|-------|------|------|
| `roberta-base` | CVE description classifier (fine-tuned) | 110M |
| `google/flan-t5-large` | Reachability reasoner | 780M |
| `microsoft/codebert-base` | Code chunk embeddings for FAISS | 125M |
| `sentence-transformers/all-MiniLM-L6-v2` | Fast fallback embeddings | 22M |

On an A100, full fine-tune of RoBERTa takes ~20-30 min on 8K examples; full pipeline inference ≈ 3-8 s per alert.

## License

MIT. See [LICENSE](LICENSE).

## Citation

```bibtex
@misc{honey2026reachabilityllm,
  author = {Ankit Kumar Honey},
  title  = {Reducing Alert Fatigue: LLM-Based False Positive Detection in Software Supply Chain Security Vulnerability Alerts},
  year   = {2026},
  note   = {CSCI E-222 Final Project, Harvard Extension School}
}
```

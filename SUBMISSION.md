# Reducing Alert Fatigue: LLM-Based False Positive Detection in Software Supply Chain Security Vulnerability Alerts

**CSCI E-222 Final Project, Harvard Extension School, Spring 2026**
**Author:** Ankit Kumar Honey
**Course topic:** Fake News and Misinformation Detection Using LLM Features
**Date:** May 16, 2026

This page is the single starting point for the project. It links to the videos, tells you how to run the notebook end to end, and points to every artifact.

---

## 1. Watch the videos first (recommended)

| Video | Link | Length | What it covers |
|---|---|---|---|
| Slide presentation | [riverside.com/shared/exported-clip/c89a2690398c012e106b](https://riverside.com/shared/exported-clip/c89a2690398c012e106b) | about 10 min | Problem framing, four-stage architecture, training methodology, results, honest limitations, future work. |
| Live demo | [riverside.com/shared/exported-clip/8ca9651df94b5022bb64](https://riverside.com/shared/exported-clip/8ca9651df94b5022bb64) | about 8 min | Walkthrough of the running Colab notebook plus a real Dependabot scan against a live GitHub repo. |

Watching both gives you the full picture in under 20 minutes without having to run anything.

---

## 2. What the project does in one paragraph

Dependabot and similar supply-chain security scanners generate millions of vulnerability alerts per day. A large fraction are technically valid but functionally irrelevant: the vulnerable function in the dependency is never reached by the consuming application, so the bug cannot be triggered. This project applies the LLM-feature methodology from the course topic (misinformation detection: is this article real or fake) to the structurally identical security question (is this alert a true positive or a false positive). A four-stage pipeline fuses a fine-tuned RoBERTa CVE classifier, a NetworkX static call graph, a Flan-T5 reachability reasoner, and a logistic regression head over a 775-dimensional combined vector. On 10,000 real advisories from the GitHub Advisory Database the full pipeline reaches F1 = 0.995 on the synthetic test set and demonstrates measurable noise reduction (around 66 to 80 percent) when run against real Dependabot alerts on a live repo.

---

## 3. How to run the notebook in Google Colab

The whole project runs in a single notebook. No local install needed.

1. Open the notebook in Colab by clicking the badge at the top of [README.md](README.md), or paste this URL into your browser:
   ```
   https://colab.research.google.com/github/honeyankit/reachability-llm/blob/main/notebooks/FalsePositive_SupplyChain_Honey.ipynb
   ```
2. In Colab, go to **Runtime > Change runtime type** and pick **A100 GPU**. Required for the RoBERTa fine-tune step. T4 will also work but the training step takes longer.
3. Click **Runtime > Run all**. The first cell installs pinned package versions and asks you to restart the runtime. Click **Runtime > Restart runtime** when prompted, then run all again.
4. The notebook clones the repo, mounts your Google Drive (optional), loads the GitHub Advisory Database, trains the RoBERTa model, builds the reachability layer, fits the combined classifier, and prints the results table.

End-to-end runtime on A100 is around 15 to 20 minutes. The bulk is RoBERTa fine-tuning (5 epochs on 30,000 advisories).

If you do not want to wait, set `MODE = "synthetic"` in the global config cell. That runs the whole notebook on a 1,000-row templated dataset in under 2 minutes. The results are illustrative, not representative.

---

## 4. Running the live Dependabot demo (Section 11 in the notebook)

The final section of the notebook scans a real GitHub repository's open Dependabot alerts, classifies each one as TRUE_POSITIVE / FALSE_POSITIVE / UNKNOWN, and prints the noise-reduction summary. To run it against your own repo you need a GitHub Personal Access Token.

### Generate a Personal Access Token

You can use either a fine-grained PAT (recommended) or a classic PAT.

**Fine-grained PAT (recommended):**

1. Go to <https://github.com/settings/personal-access-tokens/new>.
2. Set a token name (for example "reachability-llm-demo") and an expiry.
3. Under **Repository access**, pick "Only select repositories" and select the repo(s) you want to scan. For org-wide scanning, pick "All repositories" or select multiple.
4. Under **Repository permissions**, set:
   - **Dependabot alerts**: Read-only (required for the alerts endpoint)
   - **Contents**: Read-only (required for the shallow clone)
   - **Metadata**: Read-only (auto-selected)
5. For org-level scanning, also set under **Organization permissions**: **Dependabot alerts**: Read-only.
6. Generate the token. Copy it once, you cannot view it again.

**Classic PAT:**

1. Go to <https://github.com/settings/tokens/new>.
2. Pick scopes: `repo` (full), `read:org`, and `security_events`. All three are required for the alerts endpoint to return results.
3. Generate and copy the token.

### Required permission on the target repository

The Dependabot Alerts API enforces a per-repository check independent of token scopes. The authenticated user must have **admin** access on each target repo. You cannot read alerts on a repository you do not own or co-administer, regardless of how broad your PAT scopes are. For the live demo, scan a repo you own or a repo where your account has the security_manager role.

### Set the token in the notebook

In the Colab notebook, find the cell labelled "Production demo: setup + GitHub API helpers" (Section 11). Edit these three constants:

```python
GITHUB_OWNER     = "your-github-username-or-org"
GITHUB_REPO_NAME = "the-repo-you-want-to-scan"
GITHUB_TOKEN     = "ghp_PASTE_YOUR_TOKEN_HERE"
```

Or set the token as a Colab secret so it doesn't end up in the notebook. In Colab, click the key icon on the left sidebar, add a secret named `GITHUB_TOKEN`, then use:

```python
from google.colab import userdata
GITHUB_TOKEN = userdata.get("GITHUB_TOKEN")
```

Run Section 11. The first scan against a real repo with around 30 alerts takes 60 to 120 seconds and prints a summary block with the noise-reduction percentage.

---

## 5. Deliverables and where to find them

| Artifact | Path in this repo | Purpose |
|---|---|---|
| Final notebook (primary deliverable) | [`notebooks/FalsePositive_SupplyChain_Honey.ipynb`](notebooks/FalsePositive_SupplyChain_Honey.ipynb) | Trains the pipeline end to end and demonstrates the live scan. |
| Project report (15 pages) | [`reports/FalsePositive_SupplyChain_Honey.docx`](reports/FalsePositive_SupplyChain_Honey.docx) | Cover, abstract, methodology, results, discussion, limitations, references. |
| Slide deck (15 slides) | [`reports/FalsePositive_SupplyChain_Honey.pptx`](reports/FalsePositive_SupplyChain_Honey.pptx) | Course-template-conformant deck with speaker notes on every slide. |
| Pipeline source code | [`src/reachability_llm/`](src/reachability_llm/) | All modules: data loaders, models, reachability layer, visualisations. |
| Production CLI | [`scripts/scan_dependabot.py`](scripts/scan_dependabot.py) | Standalone scanner that loads the trained artifacts and runs against any repo. |
| Unit tests | [`tests/`](tests/) | 15 tests, runs in about 3 seconds via `pytest -q`. |
| Sample data | [`data/sample/`](data/sample/) | Tiny advisory and code samples that work offline. |
| Notebook builder | [`scripts/_build_notebook.py`](scripts/_build_notebook.py) | Source-of-truth Python that regenerates the notebook. |
| Report builder | [`scripts/_build_report.py`](scripts/_build_report.py) | Generates the .docx report. |
| Slide builder | [`scripts/_build_slides.py`](scripts/_build_slides.py) | Generates the .pptx deck. |
| Tech README | [`README.md`](README.md) | Technical setup, results table, project structure. |

---

## 6. Headline results

Trained on 10,000 advisories from the live GitHub Advisory Database (1,002-alert held-out test set):

| Model | F1 | Precision | Recall | ROC-AUC |
|---|---|---|---|---|
| EPSS rule baseline | 0.580 | 0.617 | 0.547 | 0.758 |
| TF-IDF + Logistic Regression | 0.607 | 0.555 | 0.670 | 0.851 |
| RoBERTa fine-tune | 0.593 | 0.578 | 0.608 | 0.828 |
| **Full pipeline (775-d fusion)** | **0.995** | **1.000** | **0.991** | **1.000** |

The full-pipeline F1 is an upper bound: the reachability features in the training set were synthesised from labels with 15 percent noise as a placeholder for a per-advisory reachability oracle. The Stage-3 reachability machinery itself is validated end-to-end on a worked CVE-2021-23337 (lodash) example in the notebook. The live Dependabot demo shows around 66 to 80 percent noise reduction on real org data, which is the deployment-relevant number.

---

## 7. Local installation (optional)

If you want to run the pipeline outside Colab:

```bash
git clone https://github.com/honeyankit/reachability-llm
cd reachability-llm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                          # 15 unit tests, about 3 seconds
python scripts/demo_lodash.py      # CVE-2021-23337 worked example
```

For the CLI scanner against your own repo:

```bash
export GITHUB_TOKEN=ghp_your_token
python scripts/scan_dependabot.py \
    --owner your-org --repo your-repo \
    --artifacts /path/to/trained/artifacts \
    --deep \
    --out reports/scan.md
```

---

## 8. Data sources

| Source | URL | Role |
|---|---|---|
| GitHub Advisory Database | <https://github.com/github/advisory-database> | Primary advisory text + ecosystem |
| FIRST EPSS | <https://www.first.org/epss/data> | Exploitation probability |
| CISA KEV catalog | <https://www.cisa.gov/known-exploited-vulnerabilities-catalog> | Confirmed-exploited CVE list (label augmentation) |
| NIST NVD | <https://nvd.nist.gov/vuln/data-feeds> | CVSS, CWE, references |

All sources are public and free. Datasets are not bundled in this repo. The notebook downloads them automatically on first run.

---

## 9. Repository

GitHub: <https://github.com/honeyankit/reachability-llm>
License: MIT

---

## 10. Contact

Ankit Kumar Honey, Engineering Manager, Dependabot, GitHub.
For questions about the project, open an issue at the repository link above.

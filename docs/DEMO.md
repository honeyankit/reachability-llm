# Demo guide

Three demos, in order of how much you want to set up.

## 1. Worked example — `demo_lodash.py`  (no GPU, no network, ~5 s)

```bash
python scripts/demo_lodash.py
```

Output: two classifications of the same CVE-2021-23337 lodash alert against two synthetic apps. App A uses `_.map`/`_.capitalize`/`_.filter` → `FALSE_POSITIVE`. App B calls `_.template(tpl, {sourceURL: req.query.src})` → `TRUE_POSITIVE`.

This is the cleanest 60-second demo for an interview / code review.

## 2. Colab notebook — `FalsePositive_SupplyChain_Honey.ipynb`

Open in Colab. With `MODE = "synthetic"` it runs end-to-end in ~5 min on CPU. With `MODE = "real"` on an A100 it pulls the full advisory DB, fine-tunes RoBERTa on ~10K examples, and produces the full results table + ROC/F1/t-SNE/confusion plots.

This is the **primary academic deliverable** for the report and grading.

## 3. Live GitHub repo scan — `scan_github_repo.py`

```bash
export GITHUB_TOKEN=ghp_…
python scripts/scan_github_repo.py \
    --repo your-org/your-repo \
    --max-alerts 100 \
    --use-llm \
    --reasoner-model google/flan-t5-base \
    --with-faiss \
    --out reports/your-repo.json
```

What you get:
- `reports/your-repo.json` — full per-alert verdict with paths, rationale, confidence.
- `reports/your-repo.md` — sorted Markdown summary; ranks `TRUE_POSITIVE` first, descending confidence.
- A noise-reduction percentage at the top: "X% of alerts can be auto-dismissed."

### Token scopes
- Public repo you own: `public_repo` + `security_events`
- Private repo: `repo` + `security_events`

### Suggested repos to demo
Pick a polyglot repo you own or have admin on with at least a dozen open Dependabot alerts. Internal Dependabot eval tenants work well. As a public sanity check, fork an old `webpack-cli`-style repo, let Dependabot enable, and scan it.

### Cost / time on a CPU laptop
- 50 alerts, repo ≤100K LOC, no LLM, no FAISS: ~30 s.
- 50 alerts, with `--use-llm` (Flan-T5-base on CPU): ~6-8 min.
- 50 alerts, with FAISS index over 1M LOC repo: ~3-5 min extra one-time index build.

On Colab A100 the LLM-on path drops to under 2 min for 50 alerts.

## Recording the 10-12 minute walkthrough video

Suggested takes:
1. `demo_lodash.py` output (1 min) — shows the core idea.
2. Notebook walkthrough (4-5 min) — focus on the four-stage table at the bottom.
3. Live scan of a repo with `scan_github_repo.py` (3-4 min) — focus on the Markdown summary and the noise-reduction %.
4. Architecture diagram + future-work slide (1-2 min).

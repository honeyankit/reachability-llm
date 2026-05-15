# Architecture

## End-to-end pipeline

```
                  ┌──────────────────────┐
                  │  CVE alert (text +   │
                  │  CVSS + EPSS + pkg)  │
                  └──────────┬───────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌───────────┐       ┌────────────┐       ┌──────────────┐
  │ Stage 1   │       │ Stage 2    │       │ Stage 3      │
  │ Baselines │       │ RoBERTa    │       │ Reachability │
  │           │       │ (768-d CLS)│       │ AST + LLM    │
  └─────┬─────┘       └─────┬──────┘       └──────┬───────┘
        │                   │                     │
        │                   │   ┌─────────────────┘
        │                   ▼   ▼
        │             ┌──────────────────────┐
        │             │  Stage 4: Combined   │
        │             │  classifier (775-d → │
        │             │  2)                  │
        │             └──────────┬───────────┘
        ▼                        ▼
   F1 ≈ 0.61              F1 ≈ 0.87
```

## Stage details

### Stage 1 — Baselines
- **EPSSRuleBaseline:** `epss >= 0.01 → TRUE_POSITIVE`. Mirrors what teams do today with no ML.
- **TfidfLogRegBaseline:** TF-IDF (uni+bi-gram, 20k feats) over advisory text → Logistic Regression. Calibrates how much signal lives in plain bag-of-words.

### Stage 2 — RoBERTa CVE classifier
- `roberta-base` (110M params), fine-tuned with `Trainer`.
- Output: 2-class probabilities + 768-d `[CLS]` embedding for downstream fusion.
- On A100: 3 epochs × 8K examples ≈ 22 min.

### Stage 3 — Reachability (core innovation)
Three layers, each falling back to the next when needed:

1. **Static call graph (NetworkX + AST)**
   - Python: `ast.NodeVisitor` walks every function, resolves call targets through import maps.
   - JavaScript/TypeScript: regex first pass (production should swap in tree-sitter).
   - `is_reachable(symbol)` does BFS/`all_simple_paths` from each entry node to any node matching the vulnerable FQN.
2. **LLM semantic reasoner (Flan-T5-large)**
   - Prompted with CVE summary + vulnerable symbol + static verdict + code excerpt.
   - Returns YES/NO plus one-sentence rationale.
   - Catches taint flow (`req.query` → vulnerable param) that pure graph reachability misses.
3. **CodeBERT + FAISS semantic fallback**
   - When static graph fails (dynamic dispatch, eval, framework hooks) or repo > 1M LOC.
   - 25-line chunks, normalized inner-product index, top-k retrieved for the LLM.

### Stage 4 — Combined classifier
- Concatenate `[768-d CLS] + [5-d structured] + [2-d reachability]` → 775-d vector.
- Default head: Logistic Regression on standardized inputs.
- Optional: 2-layer MLP (`Linear → ReLU → Dropout → Linear`) trained with AdamW.

## Source-to-package mapping

This is the hardest part of productionizing reachability and the bottleneck per the GitHub document. The project addresses it via:

- **Ecosystem-aware loaders:** ecosystem id is a feature (`ecosystem_id`). Go and JS/npm are cheap; Maven/shaded JARs are deferred to phase-3 work.
- **Curated symbol map** (`VULN_SYMBOL_MAP`) for the top CVEs with the highest alert volume.
- **AI-assisted extraction** at scan time when no curated entry exists — Flan-T5 prompt over the advisory text.
- **Confidence model:** reachability returns `reachable / unreachable / unknown` (we emit `UNKNOWN` whenever symbol mapping fails).

## Scaling

| Repo size | Strategy | Latency |
|-----------|----------|---------|
| ≤100K LOC | Full AST call graph | ~3-6 s |
| 1M LOC | Lazy AST + path-finding from candidate entries | ~25-30 s |
| 10M LOC | CodeBERT + FAISS over chunks, skip full graph | ~4 min |

## What goes into a production rollout

This repo is the academic-demo scope. A production system at Dependabot scale also needs:

- Build-time call-graph artifact storage (Action that emits CodeQL DBs on every default-branch push).
- Decoupled scan pipeline that joins current artifacts to newly-published advisories.
- Confidence calibration via labeled holdouts per ecosystem.
- Explainability surface in the alert UI (which symbol, which path).
- Alert volume / time-to-recompute / mapping-coverage metrics.

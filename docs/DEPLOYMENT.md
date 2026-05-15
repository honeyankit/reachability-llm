# Deployment notes

Production thinking notes for taking this beyond the academic submission.

## At Dependabot scale

| Layer | Demo (this repo) | Production target |
|-------|------------------|-------------------|
| Call graph | NetworkX in-process, rebuilt per scan | CodeQL DB built once per push, persisted in artifact store |
| Reasoner | Flan-T5-large per alert | Batched inference via vLLM or a hosted endpoint; cache by (repo SHA, CVE) |
| Symbol map | Curated table + regex fallback | OSV-Schema patches + AI extraction with human-in-the-loop validation |
| Code search | FAISS-CPU, in-memory | Faiss-GPU or hosted vector DB (e.g., Pinecone, pgvector) with per-org sharding |
| Pipeline | Synchronous CLI | Kafka topic `advisory.published` + worker pool that reads current call graphs |

## Two-pipeline model (per the GitHub doc)

```
                   ┌─────────────────────────────────────┐
   push event   →  │  Build pipeline                     │
                   │  - CodeQL DB                        │
                   │  - call graph extraction            │
                   │  - source-to-package fingerprint    │
                   │  → blob store + DB index            │
                   └─────────────────┬───────────────────┘
                                     │
                                     ▼
   new CVE      →  ┌─────────────────────────────────────┐
   published       │  Scan pipeline                      │
                   │  - join CVE symbol map to graph     │
                   │  - run reachability                 │
                   │  - emit alert state                 │
                   │  - explanation payload to UI        │
                   └─────────────────────────────────────┘
```

## Quality metrics to track

- Mapping coverage: % of CVEs with a symbol-level annotation.
- False-positive reduction vs the EPSS-only baseline.
- Unknown rate by ecosystem.
- Time-to-recompute after a new advisory (P50 / P95).
- Per-ecosystem confidence (Go/JS high, Maven medium until shading-aware).

## Phased rollout

Aligning with the GitHub doc's phased plan:

- **Phase 1 (MVP, Q1):** Go + JavaScript/npm only. Curated symbol map for the top 200 CVEs. Private preview to 20 internal repos. Goal: prove ≥30% noise reduction on real alerts.
- **Phase 2 (Coverage Expansion, Q2):** Scale AI symbol extraction + human review. Add Python. Backfill historical advisories.
- **Phase 3 (Hard Ecosystems, Q3–Q4):** Maven-aware analysis with shading + multi-module attribution. Elevate reachability to a first-class prioritization signal in the alert UI.

## Failure modes & mitigations

| Failure | Mitigation |
|---------|------------|
| Dynamic dispatch hides reachability | FAISS fallback; emit `UNKNOWN` rather than overconfident `unreachable` |
| Shaded/relocated classes (Maven) | Defer Java to Phase 3; until then return `UNKNOWN` for Java alerts |
| LLM hallucinates a vulnerable path | Cross-check against static graph; only emit `reachable` when both agree, otherwise `UNKNOWN` |
| Symbol mapping missing | Always return `UNKNOWN`, never `unreachable` |
| Codebase exceeds memory | Chunk + FAISS path always available; never refuse to scan |

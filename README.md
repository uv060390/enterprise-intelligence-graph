# enterprise-intelligence-graph

**A Neo4j agentic knowledge graph that stitches 8 enterprise systems into one provider
truth — agent-adjudicated entity resolution, GDS anomaly detection, and a conversational
graph analyst. Fully synthetic data.**

A public reimplementation of the enterprise knowledge-graph layer I originated at a
Fortune-500 healthcare company, where it moved provider-risk detection from weeks to
same-day. Rebuilt end-to-end on synthetic data so every layer is inspectable and
runnable. All data and metrics **in this repo** are synthetic/simulated.

## How it works

```
8 mock enterprise systems ── ticketing · ops-workflow · crm · claims-a · claims-b
   │                          · credentialing · analytics-lake · finance-mart
   ▼  ingest (idempotent)
(:SourceRecord) raw layer — one node per system record, immutable
   │
   ▼  entity resolution
deterministic keys ─► fuzzy candidates ─► LLM adjudicator on the ambiguous band
   │      RESOLVES_TO edges carry method + confidence + rationale (no anonymous merges)
   ▼
Resolved layer: (:Provider) (:Member) (:Claim) (:Ticket) (:Market) (:Code)
   │
   ├─► GDS: peer cohorts (similarity/community) + outlier scoring ─► (:AnomalyFlag)
   │        └─► alert composer agent: severity + narrative ─► (:Alert) ─► feed UI
   │
   └─► Ask-the-graph: NL question ─► guarded READ-ONLY Cypher ─► answer + cited nodes
```

Design decisions worth reading:

- **The graph's job is identity.** Anomaly math is only as good as entity resolution,
  so resolution is the heart: three stages, with the LLM ruling only on the ambiguous
  band, under an asymmetric-caution contract (uncertain ⇒ distinct/escalate, never
  guess-merge). **Zero wrong merges is a CI hard gate.**
- **GDS detects, agents explain.** Statistical machinery stays deterministic and
  auditable; the LLM does what it is best at — evidence synthesis and language.
- **The Cypher guard is code, not prompt.** Agent queries pass an allow-list
  validator + EXPLAIN pre-flight; write clauses are rejected outside the model's
  control. See [`AGENTS.md`](AGENTS.md).
- **Everything replayable offline**: committed ground truth (entity crosswalk +
  injected anomalies), recorded agent traces, snapshot-driven UI — tests and evals
  need no Neo4j credentials, API key, or luck.

Companion project: [claims-rework-agent](https://github.com/uv060390/claims-rework-agent)
— the human-in-the-loop agentic pipeline this intelligence layer complements.

## Status

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Scaffold, design contracts, Neo4j+GDS compose, CI | ✅ |
| 1 | Synthetic 8-system world + ground truth (crosswalk, injected anomalies) | ⬜ |
| 2 | 8 lightweight mock systems | ⬜ |
| 3 | Ingestion → raw SourceRecord graph | ⬜ |
| 4 | Entity resolution: keys → fuzzy → LLM adjudicator (zero-wrong-merge gate) | ⬜ |
| 5 | GDS cohorts + outlier scoring + detection eval | ⬜ |
| 6 | Graph analyst (guarded text2cypher) + alert composer | ⬜ |
| 7 | Console: graph explorer · alert feed · ask-the-graph (Vercel) | ⬜ |
| 8 | Eval harness + report | ⬜ |
| 9 | Polish & publish | ⬜ |

## Quickstart

```bash
uv sync
uv run pytest              # offline suite — no Neo4j or API key needed
docker compose up          # Neo4j 5 Community + Graph Data Science
# browser: http://localhost:7474  (neo4j / eigraphdev)
```

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and Docker.

## License

MIT

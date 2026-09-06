# CLAUDE.md — enterprise-intelligence-graph

Neo4j agentic knowledge graph unifying 8 (mock) enterprise systems: agent-assisted
entity resolution, GDS provider anomaly detection, and a conversational graph
analyst. Read `AGENTS.md` for the two agent contracts before touching `pipeline/`.

## Hard rules

1. **Synthetic data only.** Every record comes from the seeded generator in `data/`;
   the entity crosswalk and injected anomalies are committed ground truth.
2. **No employer-internal system names.** The 8 sources are referred to ONLY by class:
   ticketing, ops-workflow, crm, claims-a, claims-b, credentialing, analytics-lake,
   finance-mart. Never name the production systems or company this derives from.
3. **Agent Cypher is READ-ONLY — enforced, not requested.** Every agent-issued query
   passes the validator in `pipeline/analyst/guard.py` (allow-listed read clauses,
   schema-scoped, EXPLAIN-checked) before execution. Any change to that path needs a
   test proving write clauses (CREATE/MERGE/SET/DELETE/CALL db.*) are rejected.
4. **Zero wrong merges.** Entity resolution must never merge two distinct real-world
   providers (ground-truth crosswalk is the referee). Wrong-merge count is a CI
   hard-fail: a bad merge corrupts every downstream cohort, score, and alert.
   Uncertain pairs stay DISTINCT or ESCALATE — never guess-merge.
5. **Resolution edges carry provenance**: method (deterministic|fuzzy|agent),
   confidence, and rationale for agent adjudications. No anonymous merges.
6. Simulated metrics are labeled simulated in all docs.

## Layout

```
pipeline/    ingestion, resolution (3-stage + adjudicator agent), detection (GDS),
             analyst (text2cypher + guard), alerts, schemas, gateway
mocks/       8 lightweight FastAPI sub-apps, one per source system class
data/        synthetic 8-system generator + frozen extracts + ground truth
evals/       ER/detection/analyst evals, LLM judge, committed traces
console/     Next.js UI: graph explorer, alert feed, ask-the-graph (Vercel)
docs/        data dictionary, eval report, screenshots
tests/       pytest suite (offline; scripted LLM for agent paths)
```

## Commands

```bash
uv sync                    # deps (Python 3.11+, uv)
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pytest              # tests (no Neo4j or API key needed)
docker compose up          # Neo4j 5 community + GDS at :7474 (browser) / :7687 (bolt)
```

Neo4j local auth: `neo4j / eigraphdev` (dev-only, in docker-compose). Connection via
`NEO4J_URI` / `NEO4J_PASSWORD` env vars, defaults in `pipeline/config.py`.

## Conventions

- Python 3.11+, uv, ruff (line length 100), pytest. Pydantic models for every
  cross-boundary payload in `pipeline/schemas.py` — single source of truth.
- Graph layers: `(:SourceRecord)` per-system raw nodes are immutable after ingest;
  the resolved layer (`:Provider`, `:Member`, …) is materialized only through
  `RESOLVES_TO` edges. Detection writes `:AnomalyFlag`; alerts write `:Alert`.
- Tests never require a running Neo4j: graph-touching code goes through a thin
  repository layer that tests fake; integration tests against real Neo4j are marked
  `@pytest.mark.neo4j` and skipped when the bolt port is closed.
- Anthropic via `ANTHROPIC_API_KEY`; model in `pipeline/config.py`. Recorded traces
  in `evals/traces/` keep evals and demos key-free. Do not pass `temperature`
  (rejected by the Claude 5 family).
- Mirror project 1's proven patterns (uv/ruff/CI, snapshot-driven Vercel deploy,
  scripted-LLM offline tests): github.com/uv060390/claims-rework-agent.

## Maintenance workflows

- Changed generator? Regenerate extracts + ground truth, expect ER/detection eval
  numbers to shift, update the data dictionary.
- Changed either agent's prompt or tools? Re-record traces, re-judge, regenerate the
  eval report (all need `ANTHROPIC_API_KEY`).
- GDS algorithms must stay in the free (community) tier.

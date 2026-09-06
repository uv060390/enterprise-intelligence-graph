# AGENTS.md — agent design contracts

Two LLM agents live in this system. Neither one detects anomalies (GDS does) and
neither one can write to the graph through its query tool. Code in `pipeline/` must
match this document; update both together.

## Where intelligence lives

```
deterministic keys ─► fuzzy candidates ─► [ER adjudicator agent] ─► resolved layer
                                                                        │
                                            GDS cohorts + outlier scores (no LLM)
                                                                        │
[graph analyst agent] ◄── NL questions          [alert composer duty] ◄─┘
```

## Agent 1 — ER adjudicator (`pipeline/resolution/adjudicator.py`)

Rules only on the **ambiguous band**: candidate pairs whose fuzzy score falls between
the auto-distinct floor and the auto-merge ceiling. Deterministic key matches and
clear fuzzy scores never reach the LLM.

- Input: one candidate pair with full contextual evidence — both records verbatim,
  each side's neighborhood (other records already resolved to each entity, shared
  identifiers, activity overlap).
- Output (terminal tool call, Pydantic-validated):

```python
{
    "verdict": "merge | distinct | escalate",
    "confidence": float,  # 0-1
    "rationale": str,  # must cite specific fields from the evidence
}
```

- Constraints:
  - **Asymmetric caution**: a wrong MERGE corrupts every downstream number; a wrong
    DISTINCT only costs a duplicate. When evidence conflicts (same NPI but
    incompatible specialties/addresses/activity), the verdict is ESCALATE, never a
    coin-flip merge. CI enforces zero wrong merges against the ground-truth crosswalk.
  - The agent writes nothing. The resolver applies verdicts, stamping
    `RESOLVES_TO {method: "agent", confidence, rationale, adjudicated_at}`.
  - Failure to produce a valid verdict ⇒ ESCALATE (the safe default: a human queue).

## Agent 2 — conversational graph analyst (`pipeline/analyst/`)

The system's public face: natural-language questions answered from the graph.

- LangGraph loop: question → schema-scoped Cypher draft → **guard** → execute →
  (refine if needed) → answer with cited node IDs.
- **The guard is code, not prompt** (`pipeline/analyst/guard.py`): allow-listed
  read-only clauses (MATCH/WHERE/RETURN/WITH/ORDER/LIMIT/OPTIONAL MATCH/UNWIND and
  read-safe functions), rejects CREATE/MERGE/SET/DELETE/REMOVE/CALL outside an
  allow-list, enforces a LIMIT ceiling and an EXPLAIN pre-flight. Rejected queries
  bounce back to the agent with the reason — the agent retries or declines.
- Answers must cite the node IDs/records they derive from; the eval harness scores
  citation groundedness and text2cypher accuracy on a committed question set.
- Secondary duty — **alert composer**: for each GDS `:AnomalyFlag`, traverse the
  resolved neighborhood, judge severity (suppressing weak flags with a stated
  reason), and write narrative + recommended action via the alerts writer (its own
  module, not the guarded query tool).

## Shared rules

- One read-only Cypher execution tool, shared, guarded. No other graph access.
- Both agents terminate via a structured tool call; free-text finals are treated as
  failure and produce the safe default (ESCALATE / "cannot answer").
- Offline tests drive both graphs with a scripted chat model; real traces are
  recorded to `evals/traces/` and replayed by CI. Never assume an API key in tests.

"""Single source of truth for cross-boundary payloads.

See AGENTS.md before changing anything here: the AdjudicationVerdict schema is the
ER agent's terminal tool contract, and ResolutionEdge is the provenance every merge
must carry (CLAUDE.md hard rule 5).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

SYSTEMS = (
    "ticketing",
    "ops_workflow",
    "crm",
    "claims_a",
    "claims_b",
    "credentialing",
    "analytics_lake",
    "finance_mart",
)


class SourceRecord(BaseModel):
    """One raw record from one system — immutable after ingest."""

    system: str
    local_id: str
    entity_kind: str  # provider | member | claim | ticket | ...
    payload: dict

    @property
    def key(self) -> str:
        return f"{self.system}:{self.local_id}"


class Verdict(StrEnum):
    MERGE = "merge"
    DISTINCT = "distinct"
    ESCALATE = "escalate"


class ResolutionMethod(StrEnum):
    DETERMINISTIC = "deterministic"
    FUZZY = "fuzzy"
    AGENT = "agent"


class AdjudicationVerdict(BaseModel):
    """The ER adjudicator agent's terminal output for one candidate pair."""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class ResolutionEdge(BaseModel):
    """Provenance stamped on every RESOLVES_TO edge — no anonymous merges."""

    source_key: str  # "system:local_id"
    entity_id: str  # resolved entity node id
    method: ResolutionMethod
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None  # required when method == AGENT
    adjudicated_at: datetime | None = None

import pytest
from pydantic import ValidationError

from pipeline.schemas import (
    SYSTEMS,
    AdjudicationVerdict,
    ResolutionEdge,
    ResolutionMethod,
    SourceRecord,
    Verdict,
)


def test_eight_systems_by_class_names_only():
    assert len(SYSTEMS) == 8
    assert all(name.islower() for name in SYSTEMS)


def test_source_record_key():
    record = SourceRecord(
        system="crm", local_id="ACC-991", entity_kind="provider", payload={"name": "x"}
    )
    assert record.key == "crm:ACC-991"


def test_adjudication_verdict_roundtrip():
    verdict = AdjudicationVerdict(
        verdict=Verdict.ESCALATE,
        confidence=0.55,
        rationale="Same NPI but incompatible specialties across systems.",
    )
    assert AdjudicationVerdict.model_validate_json(verdict.model_dump_json()) == verdict


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        AdjudicationVerdict(verdict=Verdict.MERGE, confidence=1.2, rationale="x")


def test_resolution_edge_carries_provenance():
    edge = ResolutionEdge(
        source_key="claims_a:PRV-100",
        entity_id="provider:42",
        method=ResolutionMethod.AGENT,
        confidence=0.9,
        rationale="Shared NPI, matching address, overlapping activity.",
    )
    assert edge.method == ResolutionMethod.AGENT and edge.rationale

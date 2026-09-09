"""Committed ground truth — the referee for every downstream eval.

Three artifacts:

* ``crosswalk.csv`` — every system-local identifier mapped back to its true entity.
  Entity resolution is scored against this; a merge that contradicts it is a *wrong
  merge*, which CLAUDE.md hard rule 4 makes a CI hard-fail.
* ``anomalies.json`` — the twelve injected anomalous providers with their signature,
  affected months and parameters. Detection recall/precision is scored against this.
* ``er_traps.json`` — the deliberate wrong-merge bait, so an eval can report not just
  "zero wrong merges" but "zero wrong merges *on the pairs designed to cause them*".
"""

import csv
import json
from pathlib import Path

from pipeline.worldgen.extracts import (
    PROVIDER_ID_SYSTEMS,
    PROVIDER_REF_SYSTEMS,
    SYSTEMS,
    ExtractBundle,
)
from pipeline.worldgen.world import World

CROSSWALK_COLUMNS: tuple[str, ...] = ("system", "local_id", "entity_kind", "entity_id")


def build_crosswalk(world: World, bundle: ExtractBundle) -> list[dict]:
    """One row per system-local identifier emitted anywhere in the eight extracts.

    Records that carry their own provider identifier (crm accounts, both claims
    platforms' provider ids, credentialing rows, finance TINs, analytics NPIs) get an
    ``entity_kind`` of ``provider``. Ticketing and ops-workflow reference providers only
    as free text, so their rows are keyed by the ticket/request id and marked
    ``provider_ref`` — that is exactly the population the fuzzy + agent stages must earn.
    """
    members = {member.member_id: member.entity_id for member in world.members}
    rows: list[dict] = []

    for system in SYSTEMS:
        if system in PROVIDER_REF_SYSTEMS:
            for local_id, entity_id in bundle.provider_refs[system]:
                rows.append(
                    {
                        "system": system,
                        "local_id": local_id,
                        "entity_kind": "provider_ref",
                        "entity_id": entity_id,
                    }
                )
        if system in PROVIDER_ID_SYSTEMS:
            local_ids = bundle.provider_local_ids[system]
            for provider in world.providers:
                local_id = local_ids.get(provider.entity_id)
                if local_id is None:  # e.g. a provider that never billed on this platform
                    continue
                rows.append(
                    {
                        "system": system,
                        "local_id": local_id,
                        "entity_kind": "provider",
                        "entity_id": provider.entity_id,
                    }
                )
        for member_id in bundle.member_refs.get(system, []):
            rows.append(
                {
                    "system": system,
                    "local_id": member_id,
                    "entity_kind": "member",
                    "entity_id": members[member_id],
                }
            )
    return rows


def write_crosswalk(rows: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CROSSWALK_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_anomalies(world: World, path: Path) -> int:
    payload = [
        {
            "entity_id": anomaly.entity_id,
            "signature": anomaly.signature,
            "months": anomaly.months,
            "details": anomaly.details,
        }
        for anomaly in world.anomalies
    ]
    _write_json(payload, path)
    return len(payload)


def write_er_traps(world: World, path: Path) -> int:
    payload = [
        {"kind": trap.kind, "entity_ids": trap.entity_ids, "note": trap.note}
        for trap in world.traps
    ]
    _write_json(payload, path)
    return len(payload)


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_ground_truth(world: World, bundle: ExtractBundle, out_dir: Path) -> dict[str, int]:
    """Write all three ground-truth artifacts; returns row counts by file name."""
    return {
        "crosswalk.csv": write_crosswalk(build_crosswalk(world, bundle), out_dir / "crosswalk.csv"),
        "anomalies.json": write_anomalies(world, out_dir / "anomalies.json"),
        "er_traps.json": write_er_traps(world, out_dir / "er_traps.json"),
    }

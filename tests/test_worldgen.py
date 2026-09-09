"""Phase 1 acceptance tests — written against the worldgen SPEC, not the code.

The generator must produce: 8 schema-divergent extracts, a complete identity
crosswalk, a 12-provider anomaly registry whose signatures actually manifest in
the claims ledger, and the deliberate ER traps. Deterministic per seed.
"""

import json
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from pipeline.schemas import SYSTEMS
from pipeline.worldgen.world import build_world

REPO = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def outdir(tmp_path_factory):
    out = tmp_path_factory.mktemp("worldgen")
    subprocess.run(
        [sys.executable, "data/generate_world.py", "--seed", "42", "--out", str(out / "extracts")],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def extracts(outdir):
    data = {}
    for system in SYSTEMS:
        path = outdir / "extracts" / f"{system}.jsonl"
        assert path.exists(), f"missing extract for {system}"
        data[system] = [json.loads(line) for line in path.open()]
        assert data[system], f"{system} extract is empty"
    return data


@pytest.fixture(scope="module")
def ground_truth(outdir):
    gt_dir = REPO / "data" / "ground_truth"
    crosswalk = []
    with (gt_dir / "crosswalk.csv").open() as f:
        import csv as _csv

        crosswalk = list(_csv.DictReader(f))
    anomalies = json.loads((gt_dir / "anomalies.json").read_text())
    traps = json.loads((gt_dir / "er_traps.json").read_text())
    return crosswalk, anomalies, traps


@pytest.fixture(scope="module")
def world():
    return build_world(seed=42)


# ------------------------------------------------------------------ determinism


def test_deterministic_given_seed(tmp_path):
    outs = []
    for run in ("a", "b"):
        out = tmp_path / run
        subprocess.run(
            [sys.executable, "data/generate_world.py", "--seed", "7", "--out", str(out)],
            cwd=REPO,
            check=True,
            capture_output=True,
        )
        outs.append({p.name: p.read_bytes() for p in sorted(out.glob("*.jsonl"))})
    assert outs[0] == outs[1]


# ------------------------------------------------------------------- structure


def test_extract_volumes_in_bounds(extracts):
    total_claims = len(extracts["claims_a"]) + len(extracts["claims_b"])
    assert 30_000 <= total_claims <= 80_000, f"claim lines {total_claims} outside bounds"


def test_money_fields_are_cent_decimals(extracts):
    for row in extracts["claims_a"][:500]:
        for field in ("billed", "allowed", "paid"):
            value = Decimal(row[field])
            assert value == value.quantize(Decimal("0.01"))
    for row in extracts["finance_mart"][:200]:
        Decimal(row["paid_total"])


def _luhn_ok(npi: str) -> bool:
    if len(npi) != 10 or not npi.isdigit() or npi[0] not in "12":
        return False
    total = 0
    for i, ch in enumerate(reversed("80840" + npi[:9])):
        d = int(ch)
        if i % 2 == 0:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return (total + int(npi[9])) % 10 == 0


def test_npis_valid_and_never_corrupted(extracts, world):
    true_npis = {p.npi for p in world.providers}
    seen = set()
    for system, rows in extracts.items():
        for row in rows:
            for field in ("npi", "provider_npi", "prov_npi"):
                npi = row.get(field)
                if npi:
                    assert _luhn_ok(npi), f"{system}: invalid NPI {npi}"
                    assert npi in true_npis, f"{system}: NPI {npi} belongs to no true provider"
                    seen.add(npi)
    assert len(seen) > 100  # NPIs actually circulate across systems


# ------------------------------------------------------------------- crosswalk


def test_crosswalk_covers_all_carried_identifiers(extracts, ground_truth):
    crosswalk, _, _ = ground_truth
    mapped = {(r["system"], r["local_id"]) for r in crosswalk}
    checks = [
        ("crm", "account_id"),
        ("credentialing", "cred_id"),
        ("claims_a", "provider_id"),
        ("claims_b", "prov_ref"),
    ]
    for system, field in checks:
        for row in extracts[system]:
            assert (system, row[field]) in mapped, f"unmapped {system} {field}={row[field]}"


def test_crosswalk_is_consistent(ground_truth):
    crosswalk, _, _ = ground_truth
    # a system-local id maps to exactly one entity
    seen: dict[tuple, str] = {}
    for row in crosswalk:
        key = (row["system"], row["local_id"])
        assert seen.setdefault(key, row["entity_id"]) == row["entity_id"]


# ------------------------------------------------------- anomalies manifest


def _provider_monthly(world):
    """entity_id -> month -> list of claim events."""
    monthly = defaultdict(lambda: defaultdict(list))
    for event in world.claims:
        monthly[event.provider_id][event.month].append(event)
    return monthly


def test_anomaly_registry_shape(ground_truth):
    _, anomalies, _ = ground_truth
    assert len(anomalies) == 12
    by_sig = defaultdict(int)
    for a in anomalies:
        by_sig[a["signature"]] += 1
    assert by_sig == {
        "volume_spike": 3,
        "denial_surge": 3,
        "code_mix_drift": 3,
        "impossible_volume": 3,
    }


def test_volume_spike_manifests(world):
    monthly = _provider_monthly(world)
    for anomaly in world.anomalies:
        if anomaly.signature != "volume_spike":
            continue
        months = set(anomaly.months)
        normal = [len(v) for m, v in monthly[anomaly.entity_id].items() if m not in months]
        spiked = [len(v) for m, v in monthly[anomaly.entity_id].items() if m in months]
        assert spiked and normal
        assert (sum(spiked) / len(spiked)) >= 2.5 * (sum(normal) / len(normal))


def test_denial_surge_manifests(world):
    monthly = _provider_monthly(world)
    for anomaly in world.anomalies:
        if anomaly.signature != "denial_surge":
            continue
        months = set(anomaly.months)
        events = [e for m, v in monthly[anomaly.entity_id].items() if m in months for e in v]
        rate = sum(e.denied for e in events) / len(events)
        assert rate >= 0.35, f"{anomaly.entity_id} denial rate {rate:.2f} in surge months"


def test_impossible_volume_manifests(world):
    monthly = _provider_monthly(world)
    for anomaly in world.anomalies:
        if anomaly.signature != "impossible_volume":
            continue
        peak = max(sum(e.units for e in monthly[anomaly.entity_id][m]) for m in anomaly.months)
        assert peak > 900, f"{anomaly.entity_id} peak monthly units {peak}"


# ------------------------------------------------------------------- ER traps


def test_er_traps_registered(ground_truth, world):
    _, _, traps = ground_truth
    kinds = defaultdict(list)
    for trap in traps:
        kinds[trap["kind"]].append(trap)
    assert len(kinds.get("same_name_distinct", [])) >= 3
    assert len(kinds.get("name_variants_no_npi", [])) >= 4
    assert len(kinds.get("stale_address", [])) >= 3
    assert len(kinds.get("dba_payee", [])) >= 2

    providers = {p.entity_id: p for p in world.providers}
    for trap in kinds["same_name_distinct"]:
        a, b = trap["entity_ids"][:2]
        assert a != b
        assert providers[a].legal_name.split(",")[0].split()[-1].lower() != "" and (
            providers[a].legal_name != providers[b].legal_name
            or providers[a].market != providers[b].market
        )

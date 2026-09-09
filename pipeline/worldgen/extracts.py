"""Per-system extracts — the same truth, told eight inconsistent ways.

Each of the eight source systems (referred to ONLY by class, CLAUDE.md hard rule 2)
gets its own schema flavor, its own system-local identifiers and its own identity
mess: free-text name variants, missing NPIs, stale addresses, DBA payee names,
different field names and month formats.

Two invariants hold everywhere:

* **NPIs are never corrupted.** A system either carries the true NPI or omits it.
  A wrong NPI would make the ground-truth crosswalk unlearnable rather than hard.
* **Everything is deterministic.** The world's ``rng`` is threaded through, dicts
  are iterated in insertion order and nothing iterates a set.
"""

import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from random import Random

from pydantic import BaseModel

from pipeline.worldgen.catalog import (
    CRED_STATUSES,
    CRM_REPS,
    CRM_SEGMENTS,
    OPS_REQUEST_TYPES,
    OPS_STATUSES,
    TICKET_CATEGORIES,
    TICKET_STATUSES,
)
from pipeline.worldgen.world import MONTHS, ClaimEvent, TrueProvider, World

SYSTEMS: tuple[str, ...] = (
    "ticketing",
    "ops_workflow",
    "crm",
    "claims_a",
    "claims_b",
    "credentialing",
    "analytics_lake",
    "finance_mart",
)

#: Systems whose records carry the provider's own system-local identifier.
PROVIDER_ID_SYSTEMS: tuple[str, ...] = (
    "crm",
    "claims_a",
    "claims_b",
    "credentialing",
    "analytics_lake",
    "finance_mart",
)

#: Systems that reference a provider only through free text on another record.
PROVIDER_REF_SYSTEMS: tuple[str, ...] = ("ticketing", "ops_workflow")

#: Probability that a soft system (ticketing, crm) records the NPI at all.
NPI_PRESENT_RATE = 0.60

#: Probability that any emitted name string picks up whitespace/punctuation noise.
NOISE_RATE = 0.02


class ExtractBundle(BaseModel):
    """The eight extracts plus the identifier maps ground truth needs."""

    rows: dict[str, list[dict]]
    #: system -> entity_id -> that system's local provider identifier
    provider_local_ids: dict[str, dict[str, str]]
    #: system -> [(record_id, entity_id)] for free-text provider references
    provider_refs: dict[str, list[tuple[str, str]]]
    #: system -> member_ids appearing in that system, in first-seen order
    member_refs: dict[str, list[str]]

    def counts(self) -> dict[str, int]:
        return {system: len(self.rows[system]) for system in SYSTEMS}


# --------------------------------------------------------------------------------------
# Identity mangling helpers
# --------------------------------------------------------------------------------------


def _noise(rng: Random, text: str) -> str:
    """2% of emitted names pick up realistic keyboard/whitespace noise."""
    if rng.random() >= NOISE_RATE:
        return text
    style = rng.randrange(5)
    if style == 0:
        return text.replace(" ", "  ", 1)
    if style == 1:
        return f" {text}"
    if style == 2:
        return f"{text} "
    if style == 3:
        return text.replace(",", "", 1)
    return f"{text}."


def _person_variants(provider: TrueProvider) -> list[str]:
    first, last = provider.first_name, provider.last_name
    initial = provider.middle_initial
    return [
        f"{first} {last}",
        f"{last}, {first}",
        f"{last.upper()}, {first.upper()}",
        f"Dr. {first[0]}. {last}",
        f"{first} {last}, {provider.credential}",
        f"{first} {initial}. {last}",
        f"Dr. {first} {last}",
        f"{first.lower()} {last.lower()}",
    ]


def _org_variants(provider: TrueProvider) -> list[str]:
    legal, dba = provider.legal_name, provider.dba_name
    return [
        legal,
        dba,
        legal.upper(),
        legal.replace("LLC", "L.L.C.").replace("PLLC", "P.L.L.C."),
        f"{dba} ({provider.last_name})",
        f"{provider.last_name.upper()} {provider.credential}",
    ]


#: Indices into the variant lists that diverge hardest from the legal name — used for
#: the name_variants_no_npi trap providers, where free text is the only signal.
_HEAVY_PERSON_STYLES = (2, 3, 4, 7)
_HEAVY_ORG_STYLES = (2, 3, 4, 5)


def name_variant(rng: Random, provider: TrueProvider) -> str:
    """One free-text rendering of a provider's name, as a human would type it."""
    variants = _org_variants(provider) if provider.is_org else _person_variants(provider)
    if provider.heavy_name_variants:
        styles = _HEAVY_ORG_STYLES if provider.is_org else _HEAVY_PERSON_STYLES
        chosen = variants[rng.choice(styles)]
    else:
        chosen = rng.choice(variants)
    return _noise(rng, chosen)


def _sparse_local_ids(
    rng: Random, prefix: str, entity_ids: Sequence[str], width: int = 4, spread: int = 6
) -> dict[str, str]:
    """System-local ids that are sparse and NOT aligned with the true entity order.

    Aligned numbering (P-0007 -> PA-0007) would make entity resolution trivial, so each
    system numbers providers in its own shuffled order over a sparse range.
    """
    order = list(entity_ids)
    rng.shuffle(order)
    numbers = sorted(rng.sample(range(1, len(order) * spread + 1), len(order)))
    return {
        entity_id: f"{prefix}{number:0{width}d}"
        for entity_id, number in zip(order, numbers, strict=True)
    }


def _npi_or_none(rng: Random, provider: TrueProvider, rate: float = NPI_PRESENT_RATE) -> str | None:
    """The true NPI, or nothing. Never a wrong one."""
    if provider.hide_npi_in_soft_systems:
        return None
    return provider.npi if rng.random() < rate else None


def _quarter_months(quarter: int) -> tuple[str, ...]:
    return MONTHS[quarter * 3 : quarter * 3 + 3]


def _timestamp(rng: Random, month: str) -> str:
    return (
        f"{month}-{rng.randrange(1, 29):02d}T"
        f"{rng.randrange(7, 19):02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}"
    )


def _cents(value: Decimal) -> str:
    return f"{value:.2f}"


# --------------------------------------------------------------------------------------
# System 1 — ticketing (free-text provider names, NPI only sometimes)
# --------------------------------------------------------------------------------------


def build_ticketing(world: World) -> tuple[list[dict], list[tuple[str, str]]]:
    rng = world.rng
    categories = list(TICKET_CATEGORIES)
    staged: list[tuple[str, str, dict]] = []

    for provider in world.providers:
        for quarter in range(4):
            for _ in range(rng.choice((1, 2))):  # ~1.5 tickets / provider / quarter
                month = rng.choice(_quarter_months(quarter))
                category = rng.choice(categories)
                staged.append(
                    (
                        _timestamp(rng, month),
                        provider.entity_id,
                        {
                            "opened_at": "",
                            "provider_name": name_variant(rng, provider),
                            "provider_npi": _npi_or_none(rng, provider),
                            "category": category,
                            "status": rng.choice(TICKET_STATUSES),
                            "description": rng.choice(TICKET_CATEGORIES[category]),
                        },
                    )
                )

    staged.sort(key=lambda item: (item[0], item[1]))
    rows: list[dict] = []
    refs: list[tuple[str, str]] = []
    for index, (opened_at, entity_id, payload) in enumerate(staged, start=1):
        ticket_id = f"TKT-{index:05d}"
        rows.append({"ticket_id": ticket_id, **{**payload, "opened_at": opened_at}})
        refs.append((ticket_id, entity_id))
    return rows, refs


# --------------------------------------------------------------------------------------
# System 2 — ops-workflow (no NPI at all; name + market are the only handles)
# --------------------------------------------------------------------------------------


def build_ops_workflow(world: World) -> tuple[list[dict], list[tuple[str, str]]]:
    rng = world.rng
    staged: list[tuple[str, str, dict]] = []

    for provider in world.providers:
        for quarter in range(4):
            if rng.random() >= 0.5:  # ~0.5 requests / provider / quarter
                continue
            month = rng.choice(_quarter_months(quarter))
            staged.append(
                (
                    month,
                    provider.entity_id,
                    {
                        "provider_name": name_variant(rng, provider),
                        "market": provider.market,
                        "request_type": rng.choice(OPS_REQUEST_TYPES),
                        "month": month,
                        "status": rng.choice(OPS_STATUSES),
                    },
                )
            )

    staged.sort(key=lambda item: (item[0], item[1]))
    rows: list[dict] = []
    refs: list[tuple[str, str]] = []
    for index, (_, entity_id, payload) in enumerate(staged, start=1):
        request_id = f"OPS-{index:04d}"
        rows.append({"request_id": request_id, **payload})
        refs.append((request_id, entity_id))
    return rows, refs


# --------------------------------------------------------------------------------------
# System 3 — crm (one account per provider; CURRENT address, DBA-flavored name)
# --------------------------------------------------------------------------------------


def build_crm(world: World) -> tuple[list[dict], dict[str, str]]:
    rng = world.rng
    local_ids = _sparse_local_ids(rng, "ACC-", [p.entity_id for p in world.providers])
    rows: list[dict] = []

    for provider in world.providers:
        account_name = provider.dba_name if rng.random() < 0.55 else name_variant(rng, provider)
        rows.append(
            {
                "account_id": local_ids[provider.entity_id],
                "account_name": _noise(rng, account_name),
                "npi": _npi_or_none(rng, provider),
                "phone": provider.phone,
                "address": dict(provider.address),  # current, i.e. post-move
                "owner_rep": rng.choice(CRM_REPS),
                "segment": rng.choice(CRM_SEGMENTS),
            }
        )
    rows.sort(key=lambda row: row["account_id"])
    return rows, local_ids


# --------------------------------------------------------------------------------------
# Systems 4 & 5 — the two claims platforms (same facts, different schemas)
# --------------------------------------------------------------------------------------


def _ordered_claims(world: World, system: str, local_ids: dict[str, str]) -> list[ClaimEvent]:
    """Claim lines for one platform, ordered the way that platform would store them."""
    events = [event for event in world.claims if event.system == system]
    return sorted(events, key=lambda e: (e.month, local_ids[e.provider_id], e.seq))


def _first_seen_members(events: Sequence[ClaimEvent]) -> list[str]:
    seen: set[str] = set()  # membership only — never iterated
    ordered: list[str] = []
    for event in events:
        if event.member_id not in seen:
            seen.add(event.member_id)
            ordered.append(event.member_id)
    return ordered


def build_claims_a(world: World) -> tuple[list[dict], dict[str, str], list[str]]:
    rng = world.rng
    entity_ids = [p.entity_id for p in world.providers if "claims_a" in p.billing_systems]
    local_ids = _sparse_local_ids(rng, "PA-", entity_ids)
    npis = {p.entity_id: p.npi for p in world.providers}

    ordered = _ordered_claims(world, "claims_a", local_ids)
    rows = [
        {
            "claim_id": f"CA-{index:06d}",
            "provider_id": local_ids[event.provider_id],
            "npi": npis[event.provider_id],
            "member_id": event.member_id,
            "month": event.month,
            "code": event.code,
            "units": event.units,
            "billed": _cents(event.billed),
            "allowed": _cents(event.allowed),
            "paid": _cents(event.paid),
            "denied": event.denied,
            "denial_reason": event.denial_reason,
        }
        for index, event in enumerate(ordered, start=1)
    ]
    return rows, local_ids, _first_seen_members(ordered)


def build_claims_b(world: World) -> tuple[list[dict], dict[str, str], list[str]]:
    rng = world.rng
    entity_ids = [p.entity_id for p in world.providers if "claims_b" in p.billing_systems]
    local_ids = _sparse_local_ids(rng, "PB-", entity_ids)
    npis = {p.entity_id: p.npi for p in world.providers}

    ordered = _ordered_claims(world, "claims_b", local_ids)
    rows = [
        {
            "clm_ref": f"CB-{index:06d}",
            "prov_ref": local_ids[event.provider_id],
            "prov_npi": npis[event.provider_id],
            "mbr_id": event.member_id,
            # Platform B stores the service month unseparated ("202501") — one of the
            # schema quirks ingestion has to normalize.
            "svc_month": event.month.replace("-", ""),
            "proc_code": event.code,
            "qty": event.units,
            "charge_amt": _cents(event.billed),
            "allow_amt": _cents(event.allowed),
            "pay_amt": _cents(event.paid),
            "deny_flag": "Y" if event.denied else "N",
            "deny_rsn": event.denial_reason,
        }
        for index, event in enumerate(ordered, start=1)
    ]
    return rows, local_ids, _first_seen_members(ordered)


# --------------------------------------------------------------------------------------
# System 6 — credentialing (legal name + TIN; STALE address for movers)
# --------------------------------------------------------------------------------------


def build_credentialing(world: World) -> tuple[list[dict], dict[str, str]]:
    rng = world.rng
    local_ids = _sparse_local_ids(rng, "CRD-", [p.entity_id for p in world.providers])
    rows: list[dict] = []

    for provider in world.providers:
        address = provider.prior_address if provider.moved else provider.address
        year, month, day = rng.randrange(2019, 2025), rng.randrange(1, 13), rng.randrange(1, 29)
        rows.append(
            {
                "cred_id": local_ids[provider.entity_id],
                "npi": provider.npi,
                "tin": provider.tin,
                "legal_name": provider.legal_name,
                "specialty": provider.specialty,
                # Credentialing uses its own address key names.
                "address": {
                    "street": address["line1"],
                    "city": address["city"],
                    "state": address["state"],
                    "postal_code": address["zip"],
                },
                "effective_date": f"{year:04d}-{month:02d}-{day:02d}",
                "status": rng.choice(CRED_STATUSES),
            }
        )
    rows.sort(key=lambda row: row["cred_id"])
    return rows, local_ids


# --------------------------------------------------------------------------------------
# System 7 — analytics-lake (monthly aggregates keyed by NPI)
# --------------------------------------------------------------------------------------


def build_analytics_lake(world: World) -> tuple[list[dict], dict[str, str]]:
    providers = world.provider_index()
    buckets: dict[tuple[str, str, str, str], dict] = {}

    for event in world.claims:
        provider = providers[event.provider_id]
        key = (provider.npi, provider.market, event.code, event.month)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {"claim_count": 0, "unit_count": 0, "paid_sum": Decimal("0.00")}
            buckets[key] = bucket
        bucket["claim_count"] += 1
        bucket["unit_count"] += event.units
        bucket["paid_sum"] += event.paid

    ordered = sorted(buckets.items(), key=lambda item: (item[0][3], item[0][0], item[0][2]))
    rows = [
        {
            "row_id": f"ALK-{index:06d}",
            "npi": npi,
            "market": market,
            "code": code,
            "month": month,
            "claim_count": bucket["claim_count"],
            "unit_count": bucket["unit_count"],
            "paid_sum": _cents(bucket["paid_sum"]),
        }
        for index, ((npi, market, code, month), bucket) in enumerate(ordered, start=1)
    ]
    return rows, {p.entity_id: p.npi for p in world.providers}


# --------------------------------------------------------------------------------------
# System 8 — finance-mart (monthly payment rollups keyed by TIN)
# --------------------------------------------------------------------------------------


def build_finance_mart(world: World) -> tuple[list[dict], dict[str, str]]:
    providers = world.provider_index()
    buckets: dict[tuple[str, str], dict] = {}

    for event in world.claims:
        provider = providers[event.provider_id]
        key = (provider.tin, event.month)
        bucket = buckets.get(key)
        if bucket is None:
            payee = provider.dba_name if provider.finance_payee_is_dba else provider.legal_name
            bucket = {"payee_name": payee, "paid_total": Decimal("0.00"), "claim_count": 0}
            buckets[key] = bucket
        bucket["paid_total"] += event.paid
        bucket["claim_count"] += 1

    ordered = sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0]))
    rows = [
        {
            "payment_id": f"FIN-{index:05d}",
            "tin": tin,
            "payee_name": bucket["payee_name"],
            "month": month,
            "paid_total": _cents(bucket["paid_total"]),
            "claim_count": bucket["claim_count"],
        }
        for index, ((tin, month), bucket) in enumerate(ordered, start=1)
    ]
    return rows, {p.entity_id: p.tin for p in world.providers}


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


def build_extracts(world: World) -> ExtractBundle:
    """Build all eight extracts. Order matters: the shared RNG is consumed in sequence."""
    rows: dict[str, list[dict]] = {}
    provider_local_ids: dict[str, dict[str, str]] = {}
    provider_refs: dict[str, list[tuple[str, str]]] = {}
    member_refs: dict[str, list[str]] = {}

    rows["ticketing"], provider_refs["ticketing"] = build_ticketing(world)
    rows["ops_workflow"], provider_refs["ops_workflow"] = build_ops_workflow(world)
    rows["crm"], provider_local_ids["crm"] = build_crm(world)
    rows["claims_a"], provider_local_ids["claims_a"], member_refs["claims_a"] = build_claims_a(
        world
    )
    rows["claims_b"], provider_local_ids["claims_b"], member_refs["claims_b"] = build_claims_b(
        world
    )
    rows["credentialing"], provider_local_ids["credentialing"] = build_credentialing(world)
    rows["analytics_lake"], provider_local_ids["analytics_lake"] = build_analytics_lake(world)
    rows["finance_mart"], provider_local_ids["finance_mart"] = build_finance_mart(world)

    return ExtractBundle(
        rows={system: rows[system] for system in SYSTEMS},
        provider_local_ids=provider_local_ids,
        provider_refs=provider_refs,
        member_refs=member_refs,
    )


def write_jsonl(rows: Sequence[dict], path: Path) -> int:
    """Compact JSONL, one record per line, LF terminated — byte-stable for a seed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    return len(rows)


def write_extracts(bundle: ExtractBundle, out_dir: Path) -> dict[str, int]:
    """Write ``{system}.jsonl`` for all eight systems; returns row counts by system."""
    return {
        system: write_jsonl(bundle.rows[system], out_dir / f"{system}.jsonl") for system in SYSTEMS
    }

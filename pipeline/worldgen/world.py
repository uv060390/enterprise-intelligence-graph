"""The true world — what actually happened, before any system mangles it.

`build_world(seed)` produces providers, members, a twelve-month claim ledger, the
twelve injected anomalies and the deliberate entity-resolution traps. Everything is
synthetic (CLAUDE.md hard rule 1) and fully determined by the seed: a single
``random.Random`` is created here and threaded through world building and then, by
the caller, through `extracts.py`, so the same seed yields byte-identical files.

The world is the *truth*; per-system identity mess is layered on top in
`extracts.py`. Ground truth (crosswalk, anomaly registry, trap registry) is written
from this object by `ground_truth.py`.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from random import Random

from pydantic import BaseModel, ConfigDict, Field

from pipeline.worldgen.catalog import (
    BH_CODES,
    CODES,
    DENIAL_REASONS,
    FIRST_NAMES,
    HIGH_PRICE_CODES,
    LAST_NAMES,
    MARKET_CODES,
    ORG_SUFFIXES,
    ORG_WORDS,
    PHANTOM_CODE,
    SPECIALTIES,
    SPECIALTY_CREDENTIAL,
    SURGE_DENIAL_REASONS,
    TIMED_UNIT_CODES,
    make_address,
    make_npi,
    make_phone,
    make_tin,
)

MONTHS: tuple[str, ...] = tuple(f"2025-{month:02d}" for month in range(1, 13))

SIGNATURES: tuple[str, ...] = (
    "volume_spike",
    "denial_surge",
    "code_mix_drift",
    "impossible_volume",
)

TRAP_KINDS: tuple[str, ...] = (
    "same_name_distinct",
    "name_variants_no_npi",
    "stale_address",
    "dba_payee",
)

CLAIMS_A = "claims_a"
CLAIMS_B = "claims_b"

#: Markets whose providers adjudicate on claims platform A; the rest on platform B.
CLAIMS_A_MARKETS: tuple[str, ...] = ("MKT-ATX", "MKT-DFW", "MKT-PHX")

#: Share of providers that bill on BOTH claim platforms (the cross-system overlap
#: that makes entity resolution across claims_a/claims_b worth doing).
DUAL_SYSTEM_SHARE = 0.10

CENTS = Decimal("0.01")


def money(value: Decimal | float | str) -> Decimal:
    """Quantize to cents — every monetary amount in the world goes through here."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------


class TrueMember(BaseModel):
    """A member as they really are, independent of any system's copy."""

    entity_id: str  # M-000001
    member_id: str  # the enrollment identifier the claim systems carry
    name: str
    dob: str  # ISO date


class TrueProvider(BaseModel):
    """A provider as they really are, independent of any system's copy."""

    entity_id: str  # P-0001
    npi: str
    tin: str
    legal_name: str
    dba_name: str  # may differ from legal_name
    specialty: str
    market: str
    address: dict[str, str]  # CURRENT address
    prior_address: dict[str, str] | None = None  # set for movers; credentialing keeps it
    phone: str
    is_org: bool
    first_name: str
    last_name: str
    middle_initial: str
    credential: str
    panel: list[str] = Field(default_factory=list)  # member_ids
    monthly_baseline: int  # claim lines per month
    denial_base: float
    charge_multiplier: float
    allowed_pct: float
    code_weights: dict[str, float]
    billing_systems: tuple[str, ...]

    # Deliberate entity-resolution trap flags (see World.traps for the registry).
    hide_npi_in_soft_systems: bool = False  # CRM/ticketing carry no NPI at all
    heavy_name_variants: bool = False  # soft systems always use a divergent variant
    moved: bool = False  # credentialing address is stale
    finance_payee_is_dba: bool = False  # finance_mart pays the DBA, not the legal name


class Anomaly(BaseModel):
    """Ground truth for one injected anomalous provider."""

    entity_id: str
    signature: str  # one of SIGNATURES
    months: list[str]  # affected months, same format as ClaimEvent.month
    details: dict


class ERTrap(BaseModel):
    """Ground truth for one deliberate entity-resolution trap."""

    kind: str  # one of TRAP_KINDS
    entity_ids: list[str]
    note: str


class ClaimEvent(BaseModel):
    """One claim line as it really happened; systems re-name and re-shape it later."""

    seq: int  # stable emission order, used only to break ties deterministically
    provider_id: str  # TRUE entity_id, e.g. "P-0001"
    member_id: str
    system: str  # claims_a | claims_b — which platform adjudicated it
    month: str  # "2025-01"
    code: str
    units: int
    billed: Decimal
    allowed: Decimal
    paid: Decimal
    denied: bool
    denial_reason: str = ""  # empty string when not denied


class World(BaseModel):
    """Everything true about the synthetic universe for one seed."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    seed: int
    providers: list[TrueProvider]
    members: list[TrueMember]
    claims: list[ClaimEvent]
    anomalies: list[Anomaly]
    traps: list[ERTrap]
    market_top_code: dict[str, str]
    rng: Random = Field(exclude=True)

    def provider_index(self) -> dict[str, TrueProvider]:
        return {provider.entity_id: provider for provider in self.providers}

    def member_index(self) -> dict[str, TrueMember]:
        """member_id -> member (member_id is what the claim systems carry)."""
        return {member.member_id: member for member in self.members}


# --------------------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------------------


def _build_members(rng: Random, count: int) -> list[TrueMember]:
    members: list[TrueMember] = []
    seen: list[str] = []
    for index in range(1, count + 1):
        member_id = f"MB{rng.randrange(10**8):08d}"
        while member_id in seen:
            member_id = f"MB{rng.randrange(10**8):08d}"
        seen.append(member_id)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        year = rng.randrange(1948, 2013)
        month = rng.randrange(1, 13)
        day = rng.randrange(1, 29)
        members.append(
            TrueMember(
                entity_id=f"M-{index:06d}",
                member_id=member_id,
                name=f"{first} {last}",
                dob=f"{year:04d}-{month:02d}-{day:02d}",
            )
        )
    return members


# --------------------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------------------


def _base_code_weights(rng: Random) -> dict[str, float]:
    """A per-provider code mix whose two highest-priced codes stay well under 20%."""
    weights = {code: rng.uniform(1.0, 6.0) for code in CODES}
    target_high_share = rng.uniform(0.06, 0.16)
    return _tilt(weights, HIGH_PRICE_CODES, target_high_share)


def _tilt(weights: dict[str, float], codes: Sequence[str], share: float) -> dict[str, float]:
    """Rescale ``codes`` so they take exactly ``share`` of the total weight."""
    focus = sum(weights[code] for code in codes)
    other = sum(weight for code, weight in weights.items() if code not in codes)
    if focus <= 0 or other <= 0 or not 0 < share < 1:
        return dict(weights)
    scale = (share / (1.0 - share)) * other / focus
    return {code: (weight * scale if code in codes else weight) for code, weight in weights.items()}


def _build_providers(rng: Random, count: int) -> list[TrueProvider]:
    providers: list[TrueProvider] = []
    seen_npis: list[str] = []
    seen_tins: list[str] = []

    for index in range(1, count + 1):
        market = MARKET_CODES[(index - 1) % len(MARKET_CODES)]

        npi = make_npi(rng)
        while npi in seen_npis:
            npi = make_npi(rng)
        seen_npis.append(npi)

        tin = make_tin(rng)
        while tin in seen_tins:
            tin = make_tin(rng)
        seen_tins.append(tin)

        specialty = rng.choice(SPECIALTIES)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        is_org = rng.random() < 0.22

        if is_org:
            legal_name = f"{last} {rng.choice(ORG_WORDS)} {rng.choice(ORG_SUFFIXES)}"
            dba_name = f"{last} {rng.choice(ORG_WORDS)}"
        else:
            legal_name = f"{first} {last}"
            dba_name = (
                f"{first} {last} {rng.choice(ORG_WORDS)}"
                if rng.random() < 0.35
                else f"{first} {last}"
            )

        billing_systems: tuple[str, ...]
        primary = CLAIMS_A if market in CLAIMS_A_MARKETS else CLAIMS_B
        secondary = CLAIMS_B if primary == CLAIMS_A else CLAIMS_A
        billing_systems = (primary, secondary) if rng.random() < DUAL_SYSTEM_SHARE else (primary,)

        providers.append(
            TrueProvider(
                entity_id=f"P-{index:04d}",
                npi=npi,
                tin=tin,
                legal_name=legal_name,
                dba_name=dba_name,
                specialty=specialty,
                market=market,
                address=make_address(rng, market),
                phone=make_phone(rng, market),
                is_org=is_org,
                first_name=first,
                last_name=last,
                middle_initial=rng.choice("ABCDEFGHJKLMNPRSTW"),
                credential=SPECIALTY_CREDENTIAL[specialty],
                monthly_baseline=rng.randint(15, 40),
                denial_base=round(rng.uniform(0.08, 0.16), 4),
                charge_multiplier=round(rng.uniform(1.05, 1.85), 4),
                allowed_pct=round(rng.uniform(0.72, 0.94), 4),
                code_weights=_base_code_weights(rng),
                billing_systems=billing_systems,
            )
        )
    return providers


def _assign_panels(rng: Random, providers: list[TrueProvider], members: list[TrueMember]) -> None:
    member_ids = [member.member_id for member in members]
    for provider in providers:
        size = min(len(member_ids), rng.randint(30, 90))
        provider.panel = rng.sample(member_ids, size)


# --------------------------------------------------------------------------------------
# Entity-resolution traps
# --------------------------------------------------------------------------------------


def _initial_groups() -> list[list[str]]:
    """First names bucketed by initial — the raw material for name-collision traps."""
    groups: dict[str, list[str]] = {}
    for name in FIRST_NAMES:
        groups.setdefault(name[0], []).append(name)
    return [names for names in groups.values() if len(names) >= 2]


def _rename_person(provider: TrueProvider, first: str, last: str) -> None:
    provider.is_org = False
    provider.first_name = first
    provider.last_name = last
    provider.legal_name = f"{first} {last}"
    provider.dba_name = f"{first} {last}"


def _inject_er_traps(rng: Random, providers: list[TrueProvider]) -> list[ERTrap]:
    """Plant the wrong-merge bait. Trap providers are disjoint from anomalous ones."""
    traps: list[ERTrap] = []
    used: list[str] = []

    # (1) same_name_distinct — three pairs of DISTINCT providers sharing a last name and
    # a first initial, sitting in different markets. Merging either pair is a hard fail.
    by_market: dict[str, list[TrueProvider]] = {market: [] for market in MARKET_CODES}
    for provider in providers:
        by_market[provider.market].append(provider)

    market_order = list(MARKET_CODES)
    rng.shuffle(market_order)
    picks = [rng.choice(by_market[market]) for market in market_order]
    # "Sharma" is reserved for the missing-NPI cluster below, so it stays out of here.
    collision_last_names = rng.sample([name for name in LAST_NAMES if name != "Sharma"], 3)
    collision_groups = rng.sample(_initial_groups(), 3)

    for pair in range(3):
        left, right = picks[2 * pair], picks[2 * pair + 1]
        first_left, first_right = rng.sample(collision_groups[pair], 2)
        last = collision_last_names[pair]
        _rename_person(left, first_left, last)
        _rename_person(right, first_right, last)
        used.extend([left.entity_id, right.entity_id])
        traps.append(
            ERTrap(
                kind="same_name_distinct",
                entity_ids=[left.entity_id, right.entity_id],
                note=(
                    f"Distinct providers both named '{first_left[0]}. {last}' — "
                    f"{left.legal_name} in {left.market} vs {right.legal_name} in "
                    f"{right.market}. Different NPIs, TINs and panels: never merge."
                ),
            )
        )

    # (2) name_variants_no_npi — CRM and ticketing carry no NPI for these, only wildly
    # varying free-text names, so only contextual evidence can resolve them.
    remaining = [provider for provider in providers if provider.entity_id not in used]
    variant_picks = rng.sample(remaining, 4)
    # One of the four is the canonical worked example from CLAUDE.md.
    _rename_person(variant_picks[0], "Anita", "Sharma")
    variant_picks[0].dba_name = "A. Sharma LLC"
    for provider in variant_picks:
        provider.hide_npi_in_soft_systems = True
        provider.heavy_name_variants = True
        used.append(provider.entity_id)
        shapes = " / ".join(
            f"'{shape}'"
            for shape in (
                f"Dr. {provider.first_name[0]}. {provider.last_name}",
                f"{provider.last_name.upper()}, {provider.first_name.upper()}",
                f"{provider.first_name} {provider.last_name}, {provider.credential}",
            )
        )
        traps.append(
            ERTrap(
                kind="name_variants_no_npi",
                entity_ids=[provider.entity_id],
                note=(
                    f"{provider.legal_name} appears in crm and ticketing with no NPI at all "
                    f"and only divergent free-text name shapes ({shapes}); claims, "
                    "credentialing and analytics still carry the true NPI."
                ),
            )
        )

    # (3) stale_address — the provider moved; credentialing kept the old address while
    # CRM has the new one, so address similarity argues DISTINCT when it should not.
    remaining = [provider for provider in providers if provider.entity_id not in used]
    for provider in rng.sample(remaining, 3):
        provider.prior_address = provider.address
        provider.address = make_address(rng, provider.market)
        provider.moved = True
        used.append(provider.entity_id)
        traps.append(
            ERTrap(
                kind="stale_address",
                entity_ids=[provider.entity_id],
                note=(
                    f"{provider.legal_name} relocated within {provider.market}: credentialing "
                    f"still lists {provider.prior_address['line1']} while crm has "
                    f"{provider.address['line1']}."
                ),
            )
        )

    # (4) dba_payee — finance_mart pays the TIN under the DBA, not the legal name.
    remaining = [provider for provider in providers if provider.entity_id not in used]
    for provider in rng.sample(remaining, 2):
        if provider.dba_name == provider.legal_name:
            provider.dba_name = f"{provider.last_name} {rng.choice(ORG_WORDS)}"
        provider.finance_payee_is_dba = True
        used.append(provider.entity_id)
        traps.append(
            ERTrap(
                kind="dba_payee",
                entity_ids=[provider.entity_id],
                note=(
                    f"finance_mart pays TIN {provider.tin} to payee '{provider.dba_name}' "
                    f"while credentialing holds the legal name '{provider.legal_name}'."
                ),
            )
        )

    # Keep the registry grouped by kind for readable ground truth.
    traps.sort(key=lambda trap: (TRAP_KINDS.index(trap.kind), trap.entity_ids))
    return traps


def _trap_entity_ids(traps: Sequence[ERTrap]) -> list[str]:
    return [entity_id for trap in traps for entity_id in trap.entity_ids]


# --------------------------------------------------------------------------------------
# Anomalies
# --------------------------------------------------------------------------------------


def _market_top_codes(providers: Sequence[TrueProvider]) -> dict[str, str]:
    """The dominant code per market, by summed provider code weight."""
    totals: dict[str, dict[str, float]] = {
        market: dict.fromkeys(CODES, 0.0) for market in MARKET_CODES
    }
    for provider in providers:
        for code, weight in provider.code_weights.items():
            totals[provider.market][code] += weight
    return {
        market: max(CODES, key=lambda code: (per_code[code], -CODES.index(code)))
        for market, per_code in totals.items()
    }


def _select_anomalies(
    rng: Random,
    providers: Sequence[TrueProvider],
    traps: Sequence[ERTrap],
    market_top_code: dict[str, str],
) -> list[Anomaly]:
    """Twelve anomalous providers, three per signature, disjoint from the trap set."""
    trapped = _trap_entity_ids(traps)
    eligible = [provider for provider in providers if provider.entity_id not in trapped]
    chosen = rng.sample(eligible, len(SIGNATURES) * 3)

    anomalies: list[Anomaly] = []
    for offset, signature in enumerate(SIGNATURES):
        for provider in chosen[offset * 3 : offset * 3 + 3]:
            anomalies.append(
                _build_anomaly(rng, provider, signature, market_top_code[provider.market])
            )
    return anomalies


def _build_anomaly(
    rng: Random, provider: TrueProvider, signature: str, market_code: str
) -> Anomaly:
    if signature == "volume_spike":
        multiplier = round(rng.uniform(3.0, 5.0), 3)
        return Anomaly(
            entity_id=provider.entity_id,
            signature=signature,
            months=list(MONTHS[9:12]),
            details={
                "market": provider.market,
                "focus_code": market_code,
                "multiplier": multiplier,
                "baseline_claims_per_month": provider.monthly_baseline,
                "focus_code_share_in_spike": 0.7,
            },
        )

    if signature == "denial_surge":
        surge_rate = round(rng.uniform(0.45, 0.60), 4)
        return Anomaly(
            entity_id=provider.entity_id,
            signature=signature,
            months=list(MONTHS[8:12]),
            details={
                "baseline_denial_rate": provider.denial_base,
                "surge_denial_rate": surge_rate,
                "concentrated_reasons": list(SURGE_DENIAL_REASONS),
            },
        )

    if signature == "code_mix_drift":
        drift_share = round(rng.uniform(0.60, 0.75), 4)
        baseline_share = round(
            sum(provider.code_weights[code] for code in HIGH_PRICE_CODES)
            / sum(provider.code_weights.values()),
            4,
        )
        return Anomaly(
            entity_id=provider.entity_id,
            signature=signature,
            months=list(MONTHS[6:12]),
            details={
                "target_codes": list(HIGH_PRICE_CODES),
                "baseline_high_price_share": baseline_share,
                "drift_high_price_share": drift_share,
            },
        )

    # impossible_volume
    concentrated = rng.sample(provider.panel, rng.randint(4, 6))
    return Anomaly(
        entity_id=provider.entity_id,
        signature=signature,
        months=list(MONTHS[7:12]),
        details={
            "code": PHANTOM_CODE,
            "monthly_units_min": 920,
            "monthly_units_max": 980,
            "units_per_line": [3, 4],
            "concentrated_member_ids": concentrated,
            "note": (
                "Monthly 90837 units exceed 900 — more than 40 sixty-minute sessions per "
                "working day — and concentrate on a handful of members."
            ),
        },
    )


# --------------------------------------------------------------------------------------
# Claim ledger
# --------------------------------------------------------------------------------------


def _units_for(rng: Random, code: str) -> int:
    return rng.randint(2, 8) if code in TIMED_UNIT_CODES else 1


def _make_event(
    rng: Random,
    provider: TrueProvider,
    member_id: str,
    month: str,
    code: str,
    units: int,
    seq: int,
) -> ClaimEvent:
    price = BH_CODES[code][1]
    gross = price * units
    billed = money(gross * Decimal(str(provider.charge_multiplier)))
    system = (
        provider.billing_systems[0]
        if len(provider.billing_systems) == 1
        else rng.choice(provider.billing_systems)
    )
    allowed = min(billed, money(gross * Decimal(str(provider.allowed_pct))))
    paid = money(allowed * Decimal(str(round(rng.uniform(0.80, 1.0), 4))))
    return ClaimEvent(
        seq=seq,
        provider_id=provider.entity_id,
        member_id=member_id,
        system=system,
        month=month,
        code=code,
        units=units,
        billed=billed,
        allowed=allowed,
        paid=paid,
        denied=False,
    )


def _apply_denials(
    rng: Random, events: list[ClaimEvent], rate: float, reasons: Sequence[str]
) -> None:
    """Deny an exact count of lines so the injected rate is a fact, not a coin-flip."""
    if not events:
        return
    denied_count = int(round(rate * len(events)))
    denied_count = max(0, min(len(events), denied_count))
    for position in sorted(rng.sample(range(len(events)), denied_count)):
        event = events[position]
        event.denied = True
        event.denial_reason = rng.choice(reasons)
        event.allowed = money(0)
        event.paid = money(0)


def _build_ledger(
    rng: Random, providers: Sequence[TrueProvider], anomalies: Sequence[Anomaly]
) -> list[ClaimEvent]:
    by_entity = {anomaly.entity_id: anomaly for anomaly in anomalies}
    ledger: list[ClaimEvent] = []

    for provider in providers:
        anomaly = by_entity.get(provider.entity_id)
        for month in MONTHS:
            affected = anomaly is not None and month in anomaly.months
            signature = anomaly.signature if anomaly else ""
            details = anomaly.details if anomaly else {}

            volume = max(5, provider.monthly_baseline + rng.randint(-3, 3))
            weights = dict(provider.code_weights)
            denial_rate = provider.denial_base
            reasons: Sequence[str] = DENIAL_REASONS

            if affected and signature == "volume_spike":
                volume = int(round(volume * details["multiplier"]))
                weights = _tilt(
                    weights, (details["focus_code"],), details["focus_code_share_in_spike"]
                )
            elif affected and signature == "denial_surge":
                denial_rate = details["surge_denial_rate"]
                reasons = details["concentrated_reasons"]
            elif affected and signature == "code_mix_drift":
                weights = _tilt(weights, HIGH_PRICE_CODES, details["drift_high_price_share"])

            codes = list(weights)
            picks = rng.choices(codes, weights=[weights[code] for code in codes], k=volume)
            month_events: list[ClaimEvent] = []
            for code in picks:
                month_events.append(
                    _make_event(
                        rng,
                        provider,
                        rng.choice(provider.panel),
                        month,
                        code,
                        _units_for(rng, code),
                        len(ledger) + len(month_events),
                    )
                )

            if affected and signature == "impossible_volume":
                target_units = rng.randint(
                    details["monthly_units_min"], details["monthly_units_max"]
                )
                low, high = details["units_per_line"]
                emitted = 0
                while emitted < target_units:
                    units = min(rng.randint(low, high), target_units - emitted)
                    month_events.append(
                        _make_event(
                            rng,
                            provider,
                            rng.choice(details["concentrated_member_ids"]),
                            month,
                            details["code"],
                            units,
                            len(ledger) + len(month_events),
                        )
                    )
                    emitted += units

            _apply_denials(rng, month_events, denial_rate, reasons)
            ledger.extend(month_events)

    return ledger


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def build_world(seed: int, n_providers: int = 160, n_members: int = 2400) -> World:
    """Build the whole synthetic universe deterministically from ``seed``."""
    rng = Random(seed)
    members = _build_members(rng, n_members)
    providers = _build_providers(rng, n_providers)
    _assign_panels(rng, providers, members)
    traps = _inject_er_traps(rng, providers)
    market_top_code = _market_top_codes(providers)
    anomalies = _select_anomalies(rng, providers, traps, market_top_code)
    claims = _build_ledger(rng, providers, anomalies)
    return World(
        seed=seed,
        providers=providers,
        members=members,
        claims=claims,
        anomalies=anomalies,
        traps=traps,
        market_top_code=market_top_code,
        rng=rng,
    )

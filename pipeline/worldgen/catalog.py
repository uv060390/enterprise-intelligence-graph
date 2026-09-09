"""Reference data for the synthetic behavioral-health world.

Everything in this module is invented (CLAUDE.md hard rule 1): the codes are real
public CPT/HCPCS identifiers, but the prices, markets, names, addresses and phone
numbers are fabricated for the generator. No employer-internal system, provider or
member appears here.

All randomness flows through a caller-supplied ``random.Random`` so the whole world
is reproducible from one seed.
"""

from decimal import Decimal
from random import Random

# --------------------------------------------------------------------------------------
# Service codes
# --------------------------------------------------------------------------------------

# code -> (description, unit_price)
BH_CODES: dict[str, tuple[str, Decimal]] = {
    "90791": ("Psychiatric diagnostic evaluation", Decimal("180.00")),
    "90792": ("Psychiatric diagnostic evaluation with medical services", Decimal("220.00")),
    "90832": ("Psychotherapy, 30 minutes", Decimal("75.00")),
    "90834": ("Psychotherapy, 45 minutes", Decimal("110.00")),
    "90837": ("Psychotherapy, 60 minutes", Decimal("160.00")),
    "90839": ("Psychotherapy for crisis, first 60 minutes", Decimal("195.00")),
    "90846": ("Family psychotherapy without patient present", Decimal("125.00")),
    "90847": ("Family psychotherapy with patient present", Decimal("135.00")),
    "90853": ("Group psychotherapy", Decimal("45.00")),
    "96130": ("Psychological testing evaluation, first hour", Decimal("145.00")),
    "H0004": ("Behavioral health counseling and therapy, per 15 minutes", Decimal("28.50")),
    "H2019": ("Therapeutic behavioral services, per 15 minutes", Decimal("32.75")),
}

CODES: tuple[str, ...] = tuple(BH_CODES)

#: Codes billed in 15-minute increments — these legitimately carry units > 1.
TIMED_UNIT_CODES: tuple[str, ...] = ("H0004", "H2019")

#: The two highest-priced codes; ``code_mix_drift`` shifts billing onto these.
HIGH_PRICE_CODES: tuple[str, ...] = tuple(
    code for code, _ in sorted(BH_CODES.items(), key=lambda kv: (-kv[1][1], kv[0]))[:2]
)

#: The code the ``impossible_volume`` signature over-bills.
PHANTOM_CODE = "90837"

DENIAL_REASONS: tuple[str, ...] = (
    "CO-16 claim lacks information needed for adjudication",
    "CO-18 exact duplicate claim or service",
    "CO-27 expenses incurred after coverage terminated",
    "CO-29 time limit for filing has expired",
    "CO-45 charge exceeds fee schedule or contracted amount",
    "CO-50 not deemed a medical necessity by the payer",
    "CO-97 benefit included in payment for another service",
    "CO-197 precertification or authorization absent",
    "CO-11 diagnosis inconsistent with the procedure",
    "PR-1 deductible amount",
)

#: Reasons a denial surge concentrates on (a real surge is rarely diffuse).
SURGE_DENIAL_REASONS: tuple[str, ...] = (
    "CO-197 precertification or authorization absent",
    "CO-16 claim lacks information needed for adjudication",
)

# --------------------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------------------

MARKETS: tuple[tuple[str, str], ...] = (
    ("MKT-ATX", "Austin TX"),
    ("MKT-DFW", "Dallas-Fort Worth TX"),
    ("MKT-PHX", "Phoenix AZ"),
    ("MKT-DEN", "Denver CO"),
    ("MKT-MSP", "Minneapolis-St Paul MN"),
    ("MKT-CLT", "Charlotte NC"),
)

MARKET_CODES: tuple[str, ...] = tuple(code for code, _ in MARKETS)
MARKET_NAMES: dict[str, str] = dict(MARKETS)

#: market -> ((city, state, zip), ...)
MARKET_CITIES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "MKT-ATX": (
        ("Austin", "TX", "78701"),
        ("Round Rock", "TX", "78664"),
        ("Cedar Park", "TX", "78613"),
        ("Pflugerville", "TX", "78660"),
    ),
    "MKT-DFW": (
        ("Dallas", "TX", "75201"),
        ("Fort Worth", "TX", "76102"),
        ("Plano", "TX", "75024"),
        ("Arlington", "TX", "76010"),
    ),
    "MKT-PHX": (
        ("Phoenix", "AZ", "85004"),
        ("Mesa", "AZ", "85201"),
        ("Scottsdale", "AZ", "85251"),
        ("Tempe", "AZ", "85281"),
    ),
    "MKT-DEN": (
        ("Denver", "CO", "80202"),
        ("Aurora", "CO", "80012"),
        ("Lakewood", "CO", "80226"),
        ("Boulder", "CO", "80301"),
    ),
    "MKT-MSP": (
        ("Minneapolis", "MN", "55401"),
        ("Saint Paul", "MN", "55101"),
        ("Bloomington", "MN", "55420"),
        ("Edina", "MN", "55435"),
    ),
    "MKT-CLT": (
        ("Charlotte", "NC", "28202"),
        ("Concord", "NC", "28025"),
        ("Gastonia", "NC", "28052"),
        ("Huntersville", "NC", "28078"),
    ),
}

CITIES: tuple[str, ...] = tuple(
    city for market in MARKET_CODES for city, _, _ in MARKET_CITIES[market]
)

MARKET_AREA_CODES: dict[str, str] = {
    "MKT-ATX": "512",
    "MKT-DFW": "214",
    "MKT-PHX": "602",
    "MKT-DEN": "303",
    "MKT-MSP": "612",
    "MKT-CLT": "704",
}

STREETS: tuple[str, ...] = (
    "Cedar Ridge Dr",
    "Lakeview Blvd",
    "Hillcrest Ave",
    "Summit Park Way",
    "Prairie Creek Rd",
    "Willow Bend Ln",
    "Copper Mill Rd",
    "Stonebridge Ct",
    "Harborview Dr",
    "Meridian Loop",
    "Juniper Hollow Way",
    "Foxglove Ter",
    "Old Mill Rd",
    "Northgate Pkwy",
    "Silver Sage Trl",
    "Brookfield Ave",
)

SUITE_FORMS: tuple[str, ...] = ("Ste {n}", "Suite {n}", "Unit {n}", "Bldg {n}")

# --------------------------------------------------------------------------------------
# People and practices
# --------------------------------------------------------------------------------------

SPECIALTIES: tuple[str, ...] = (
    "psychiatry",
    "clinical psychology",
    "LCSW counseling",
    "addiction medicine",
    "child & adolescent psychiatry",
    "marriage & family therapy",
    "psychiatric nursing",
    "applied behavior analysis",
)

SPECIALTY_CREDENTIAL: dict[str, str] = {
    "psychiatry": "MD",
    "clinical psychology": "PhD",
    "LCSW counseling": "LCSW",
    "addiction medicine": "MD",
    "child & adolescent psychiatry": "MD",
    "marriage & family therapy": "LMFT",
    "psychiatric nursing": "PMHNP",
    "applied behavior analysis": "BCBA",
}

# First names are deliberately clustered by initial: shared-initial pairs are the raw
# material for the "same last name + same first initial" entity-resolution traps.
FIRST_NAMES: tuple[str, ...] = (
    "Anita",
    "Arjun",
    "Beatriz",
    "Brandon",
    "Camila",
    "Carlos",
    "Daniel",
    "Dana",
    "Elena",
    "Ethan",
    "Farida",
    "Grace",
    "Hassan",
    "Imani",
    "Jordan",
    "Jasmine",
    "Kevin",
    "Karen",
    "Linh",
    "Marcus",
    "Maria",
    "Nadia",
    "Omar",
    "Priya",
    "Paul",
    "Rosa",
    "Samuel",
    "Sofia",
    "Thomas",
    "Yuki",
)

LAST_NAMES: tuple[str, ...] = (
    "Alvarez",
    "Bhatt",
    "Calderon",
    "Diallo",
    "Espinoza",
    "Fitzgerald",
    "Grant",
    "Hoffman",
    "Ibrahim",
    "Jensen",
    "Kowalski",
    "Lundqvist",
    "Mbeki",
    "Nakamura",
    "Okafor",
    "Petrov",
    "Quintero",
    "Ramirez",
    "Sharma",
    "Tran",
    "Underwood",
    "Vasquez",
    "Whitfield",
    "Xiong",
    "Yamamoto",
    "Zielinski",
)

ORG_WORDS: tuple[str, ...] = (
    "Behavioral Health",
    "Counseling",
    "Psychiatric Associates",
    "Wellness Partners",
    "Mind & Mood",
    "Family Therapy",
    "Recovery Services",
)

ORG_SUFFIXES: tuple[str, ...] = ("LLC", "PLLC", "PC", "Group", "Inc")

# --------------------------------------------------------------------------------------
# Per-system vocabularies
# --------------------------------------------------------------------------------------

TICKET_CATEGORIES: dict[str, tuple[str, ...]] = {
    "claim status inquiry": (
        "Provider office calling on unpaid claims from last month.",
        "Requesting status on a batch of pended claim lines.",
        "Office manager asking why remittance has not posted.",
    ),
    "roster update": (
        "Add a new clinician to the group roster.",
        "Roster shows a clinician who left the practice.",
        "Requesting panel roster refresh for the market.",
    ),
    "credentialing follow-up": (
        "Revalidation packet submitted, awaiting confirmation.",
        "Asking for status of an initial credentialing application.",
        "Licence expiry mismatch reported by the practice.",
    ),
    "payment discrepancy": (
        "Paid amount does not match the contracted fee schedule.",
        "Underpayment reported across several sessions.",
        "Duplicate recoupment applied to a prior payment.",
    ),
    "address change": (
        "Practice relocated, directory still lists the old suite.",
        "Requesting update of the service location on file.",
        "Mail returned undeliverable at the address on record.",
    ),
    "portal access": (
        "User locked out of the provider portal.",
        "Requesting an additional portal login for office staff.",
        "Multi-factor reset requested for the billing user.",
    ),
    "authorization question": (
        "Asking whether an authorization is required for the service.",
        "Authorization was approved but the claim still denied.",
        "Requesting an extension on an existing authorization.",
    ),
    "fee schedule question": (
        "Requesting a copy of the current fee schedule.",
        "Question about the rate for a timed service code.",
        "Disputing the allowed amount on a group session.",
    ),
}

TICKET_STATUSES: tuple[str, ...] = ("open", "pending", "resolved", "closed", "closed")

OPS_REQUEST_TYPES: tuple[str, ...] = (
    "panel roster refresh",
    "market realignment",
    "contract amendment",
    "directory correction",
    "network adequacy review",
    "fee schedule load",
)

OPS_STATUSES: tuple[str, ...] = ("submitted", "in_review", "approved", "rejected", "completed")

CRM_SEGMENTS: tuple[str, ...] = ("strategic", "growth", "standard", "watch")

CRM_REPS: tuple[str, ...] = (
    "R. Delacroix",
    "T. Okonjo",
    "M. Halvorsen",
    "S. Kaur",
    "J. Barrera",
    "L. Whitmore",
    "P. Nkemelu",
    "A. Lindgren",
)

CRED_STATUSES: tuple[str, ...] = (
    "active",
    "active",
    "active",
    "active",
    "pending_revalidation",
    "expired",
)

# --------------------------------------------------------------------------------------
# Identifier factories
# --------------------------------------------------------------------------------------

_NPI_LUHN_PREFIX = "80840"


def _luhn_check_digit(payload: str) -> int:
    """Luhn check digit for ``payload`` (which excludes the check digit itself)."""
    total = 0
    for position, char in enumerate(reversed(payload)):
        digit = int(char)
        if position % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - total % 10) % 10


def make_npi(rng: Random) -> str:
    """A 10-digit NPI: starts 1 or 2, check digit valid over "80840" + first nine."""
    base = rng.choice("12") + "".join(str(rng.randrange(10)) for _ in range(8))
    return base + str(_luhn_check_digit(_NPI_LUHN_PREFIX + base))


def is_valid_npi(npi: str) -> bool:
    """True when ``npi`` is 10 digits with a correct Luhn check digit."""
    if len(npi) != 10 or not npi.isdigit() or npi[0] not in "12":
        return False
    return _luhn_check_digit(_NPI_LUHN_PREFIX + npi[:9]) == int(npi[9])


def make_tin(rng: Random) -> str:
    """A 9-digit employer identification number formatted ``XX-XXXXXXX``."""
    return f"{rng.randrange(10, 100):02d}-{rng.randrange(10**7):07d}"


def make_phone(rng: Random, market: str) -> str:
    """A market-plausible phone number in the reserved 555-01xx exchange."""
    return f"({MARKET_AREA_CODES[market]}) 555-{rng.randrange(100, 200):04d}"


def make_address(rng: Random, market: str) -> dict[str, str]:
    """A street address inside ``market``."""
    city, state, postal = rng.choice(MARKET_CITIES[market])
    line1 = f"{rng.randrange(100, 9900)} {rng.choice(STREETS)}"
    if rng.random() < 0.45:
        line1 += " " + rng.choice(SUITE_FORMS).format(n=rng.randrange(100, 900))
    return {"line1": line1, "city": city, "state": state, "zip": postal}

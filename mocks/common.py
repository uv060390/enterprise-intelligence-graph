"""Shared plumbing for the eight mock source-system APIs.

The point of these mocks is that they are *deliberately inconsistent*: eight different
auth schemes, pagination dialects, envelope shapes and payload formats, so Phase 3's
ingestion has to do honest per-system integration work. Everything that is genuinely
shared — record loading, auth constants, the two uniform introspection endpoints —
lives here; everything that differs lives in ``mocks/systems/<system>.py``.

All data is synthetic (CLAUDE.md hard rule 1) and every system is named only by class
(hard rule 2).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from pipeline.worldgen.extracts import SYSTEMS

__all__ = [
    "SYSTEMS",
    "TICKETING_API_KEY",
    "TICKETING_API_KEY_HEADER",
    "CRM_BEARER_TOKEN",
    "FINANCE_USERNAME",
    "FINANCE_PASSWORD",
    "STORE",
    "RecordStore",
    "extracts_dir",
    "add_common_routes",
    "filter_by_month",
    "unauthorized",
]

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------------------
# Auth constants — dev-only, deliberately different per system. Tests import these.
# --------------------------------------------------------------------------------------

#: ticketing: static API key in a custom header.
TICKETING_API_KEY_HEADER = "X-Api-Key"
TICKETING_API_KEY = "ticketing-dev-key"

#: crm: bearer token in the standard Authorization header.
CRM_BEARER_TOKEN = "crm-dev-token"

#: finance-mart: HTTP Basic.
FINANCE_USERNAME = "finance"
FINANCE_PASSWORD = "finance-dev"


def unauthorized(detail: str, *, basic: bool = False) -> HTTPException:
    """401 with the right challenge header for the scheme that rejected the call."""
    headers = {"WWW-Authenticate": 'Basic realm="finance-mart"'} if basic else None
    return HTTPException(status_code=401, detail=detail, headers=headers)


# --------------------------------------------------------------------------------------
# Record loading
# --------------------------------------------------------------------------------------


def extracts_dir() -> Path:
    """Directory holding ``{system}.jsonl``. Overridable via ``EXTRACTS_DIR``."""
    raw = os.environ.get("EXTRACTS_DIR")
    return Path(raw).expanduser().resolve() if raw else REPO_ROOT / "data" / "extracts"


#: Seed the mocks regenerate with when the extracts are missing. Must match the seed
#: the committed ground truth was built from (data/generate_world.py --seed 42).
WORLDGEN_SEED = 42


def _generate_extracts(out_dir: Path) -> None:
    """Rebuild the frozen extracts from the Phase 1 generator.

    The extracts are not committed (they regenerate byte-identically from the seed), so a
    fresh clone or a fresh container has nothing on disk. Rather than fail to boot, run the
    same code path as ``data/generate_world.py`` and write the eight JSONL files.
    """
    from pipeline.worldgen.extracts import build_extracts, write_extracts
    from pipeline.worldgen.world import build_world

    world = build_world(WORLDGEN_SEED)
    write_extracts(build_extracts(world), out_dir)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class RecordStore:
    """In-memory home for the eight extracts.

    Loading is lazy *and* eager: the app's lifespan warms it at startup (so ``uvicorn``
    and docker pay the generation cost once, before serving), while every read also
    calls :meth:`ensure_loaded`, so a ``TestClient(app)`` used without its lifespan
    context manager still sees data.
    """

    def __init__(self) -> None:
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._source: Path | None = None

    @property
    def source(self) -> Path | None:
        """Directory the currently held records were read from."""
        return self._source

    def ensure_loaded(self) -> None:
        directory = extracts_dir()
        if self._rows and self._source == directory:
            return
        self.load(directory)

    def load(self, directory: Path) -> None:
        """Read all eight extracts, generating them first if any file is missing."""
        if any(not (directory / f"{system}.jsonl").exists() for system in SYSTEMS):
            _generate_extracts(directory)
        self._rows = {system: _read_jsonl(directory / f"{system}.jsonl") for system in SYSTEMS}
        self._source = directory

    def rows(self, system: str) -> list[dict[str, Any]]:
        self.ensure_loaded()
        return self._rows[system]

    def counts(self) -> dict[str, int]:
        self.ensure_loaded()
        return {system: len(self._rows[system]) for system in SYSTEMS}


#: Process-wide record store shared by every sub-app.
STORE = RecordStore()


# --------------------------------------------------------------------------------------
# Uniform bits: the only two endpoints every system agrees on
# --------------------------------------------------------------------------------------


def add_common_routes(app: FastAPI, system: str) -> None:
    """Attach ``/health`` and ``/_inventory`` — deliberately unauthenticated everywhere.

    Health checks that need a credential are useless to an orchestrator, and ingestion
    uses ``/_inventory`` to discover a system's shape before it can prove it can read it.
    """

    @app.get("/health", tags=["common"])
    def health() -> dict[str, Any]:
        return {"status": "ok", "system": system, "records": len(STORE.rows(system))}

    @app.get("/_inventory", tags=["common"])
    def inventory() -> dict[str, Any]:
        rows = STORE.rows(system)
        return {
            "system": system,
            "record_count": len(rows),
            "fields": sorted(rows[0]) if rows else [],
        }


def filter_by_month(
    rows: list[dict[str, Any]], month: str | None, field: str = "month"
) -> list[dict[str, Any]]:
    """Filter rows on an exact month-string match, or pass them through when unset."""
    if month is None:
        return rows
    return [row for row in rows if row.get(field) == month]

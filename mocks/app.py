"""The mock enterprise estate: eight source-system APIs in one process.

    uv run uvicorn mocks.app:app --port 8010

Each system is mounted as its own sub-app under ``/{system}`` and speaks its own dialect
(auth scheme, pagination style, envelope shape, payload format). The uniform surface is
deliberately tiny — ``/{system}/health`` and ``/{system}/_inventory`` — so Phase 3's
ingestion has to write real per-system integration code instead of one generic loop.

All data is synthetic (CLAUDE.md hard rule 1); systems are named only by class (rule 2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from mocks.common import STORE, SYSTEMS, extracts_dir
from mocks.systems import SUB_APPS


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Warm the record store before serving.

    Extracts are not committed (they regenerate byte-identically from seed 42), so on a
    fresh clone or container this generates them once, at startup, rather than making the
    first request pay for it.
    """
    STORE.load(extracts_dir())
    yield


app = FastAPI(
    title="Enterprise Intelligence Graph — mock source systems",
    description=__doc__,
    version="0.1.0",
    lifespan=lifespan,
)

for mount_path, sub_app in SUB_APPS.items():
    app.mount(f"/{mount_path}", sub_app, name=mount_path)


@app.get("/", tags=["meta"])
def index() -> dict[str, Any]:
    """Directory of the estate: where each system lives and how big it is."""
    counts = STORE.counts()
    return {
        "systems": [
            {
                "system": system,
                "base_path": f"/{system}",
                "health": f"/{system}/health",
                "inventory": f"/{system}/_inventory",
                "records": counts[system],
            }
            for system in SYSTEMS
        ],
        "extracts_dir": str(STORE.source or extracts_dir()),
    }


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    """Aggregate health: ok only when all eight systems have records loaded."""
    counts = STORE.counts()
    return {
        "status": "ok" if all(counts.values()) else "degraded",
        "systems": counts,
    }

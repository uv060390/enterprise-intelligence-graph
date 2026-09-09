"""Mock credentialing API.

Dialect: no auth and no pagination — it hands back the whole roster in one shot — but it
refuses to answer without an ``as_of`` date, because credentialing status is only
meaningful at a point in time. Missing/malformed ``as_of`` is a 400 (not FastAPI's
default 422): this system predates anyone's validation conventions.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query

from mocks.common import STORE, add_common_routes

SYSTEM = "credentialing"

app = FastAPI(
    title="mock credentialing API",
    description="Synthetic credentialing system: mandatory as_of date, unpaginated roster.",
)
add_common_routes(app, SYSTEM)


def parse_as_of(as_of: str | None) -> date:
    if as_of is None:
        raise HTTPException(
            status_code=400,
            detail="query parameter 'as_of' is required, in YYYY-MM-DD form",
        )
    try:
        return date.fromisoformat(as_of)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"query parameter 'as_of' must be YYYY-MM-DD, got {as_of!r}",
        ) from exc


@app.get("/records")
def list_records(
    as_of: Annotated[str | None, Query(description="required, YYYY-MM-DD")] = None,
) -> dict[str, Any]:
    effective = parse_as_of(as_of)
    return {"as_of": effective.isoformat(), "records": STORE.rows(SYSTEM)}

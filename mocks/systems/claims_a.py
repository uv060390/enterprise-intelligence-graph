"""Mock claims platform A API.

Dialect: no auth; offset/limit pagination inside a ``data`` envelope, with an optional
``month`` filter in ISO ``YYYY-MM`` form. ``total`` reflects the filter, not the table.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Query

from mocks.common import STORE, add_common_routes, filter_by_month

SYSTEM = "claims_a"

app = FastAPI(
    title="mock claims-A API",
    description="Synthetic claims platform A: unauthenticated, offset/limit, ISO months.",
)
add_common_routes(app, SYSTEM)


@app.get("/claims")
def list_claims(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    month: Annotated[str | None, Query(description="ISO month, e.g. 2025-01")] = None,
) -> dict[str, Any]:
    rows = filter_by_month(STORE.rows(SYSTEM), month)
    return {"data": rows[offset : offset + limit], "total": len(rows)}

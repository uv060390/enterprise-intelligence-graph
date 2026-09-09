"""Mock ticketing API.

Dialect: static API key in ``X-Api-Key``; offset/limit pagination with a hard limit
ceiling of 100 rows per page and a count-bearing envelope.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Query

from mocks.common import STORE, TICKETING_API_KEY, add_common_routes, unauthorized

SYSTEM = "ticketing"

app = FastAPI(
    title="mock ticketing API",
    description="Synthetic ticketing system: API-key auth, offset/limit pagination.",
)
add_common_routes(app, SYSTEM)


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key != TICKETING_API_KEY:
        raise unauthorized("missing or invalid X-Api-Key")


@app.get("/tickets", dependencies=[Depends(require_api_key)])
def list_tickets(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    rows = STORE.rows(SYSTEM)
    return {
        "tickets": rows[offset : offset + limit],
        "total": len(rows),
        "offset": offset,
        "limit": limit,
    }

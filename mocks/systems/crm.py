"""Mock CRM API.

Dialect: bearer-token auth; opaque-cursor pagination. The cursor is base64 of the next
row index, but clients must treat it as opaque — the only contract is "send back what
you were given, stop when ``next_cursor`` is null".
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from mocks.common import CRM_BEARER_TOKEN, STORE, add_common_routes, unauthorized

SYSTEM = "crm"

app = FastAPI(
    title="mock CRM API",
    description="Synthetic CRM system: bearer auth, opaque cursor pagination.",
)
add_common_routes(app, SYSTEM)


def require_bearer(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = f"Bearer {CRM_BEARER_TOKEN}"
    if authorization != expected:
        raise unauthorized("missing or invalid bearer token")


def encode_cursor(index: int) -> str:
    return base64.urlsafe_b64encode(str(index).encode()).decode()


def decode_cursor(cursor: str, total: int) -> int:
    """Opaque cursor -> row index. Anything unparseable or out of range is a 400."""
    try:
        index = int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail=f"invalid cursor: {cursor!r}") from exc
    if index < 0 or index > total:
        raise HTTPException(status_code=400, detail=f"cursor out of range: {cursor!r}")
    return index


@app.get("/accounts", dependencies=[Depends(require_bearer)])
def list_accounts(
    cursor: Annotated[str | None, Query()] = None,
    batch: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> dict[str, Any]:
    rows = STORE.rows(SYSTEM)
    start = decode_cursor(cursor, len(rows)) if cursor is not None else 0
    end = start + batch
    return {
        "records": rows[start:end],
        "next_cursor": encode_cursor(end) if end < len(rows) else None,
    }

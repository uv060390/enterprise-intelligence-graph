"""Mock finance-mart API.

Dialect: HTTP Basic auth and a flat CSV file download — no JSON anywhere. Every value
renders as a string, so downstream ingestion has to re-type amounts and counts itself.
"""

from __future__ import annotations

import csv
import io
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from mocks.common import (
    FINANCE_PASSWORD,
    FINANCE_USERNAME,
    STORE,
    add_common_routes,
    filter_by_month,
    unauthorized,
)

SYSTEM = "finance_mart"

app = FastAPI(
    title="mock finance-mart API",
    description="Synthetic finance mart: HTTP Basic auth, CSV download.",
)
add_common_routes(app, SYSTEM)

#: ``auto_error=False`` so a missing header lands on our 401 rather than FastAPI's 403.
_basic = HTTPBasic(auto_error=False)


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    if credentials is None:
        raise unauthorized("missing basic credentials", basic=True)
    # Compare both halves unconditionally (no short-circuit) and on bytes, so a
    # non-ASCII credential can't blow up compare_digest.
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), FINANCE_USERNAME.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), FINANCE_PASSWORD.encode("utf-8")
    )
    if not (user_ok and password_ok):
        raise unauthorized("invalid basic credentials", basic=True)


@app.get("/payments.csv", dependencies=[Depends(require_basic_auth)])
def payments_csv(
    month: Annotated[str | None, Query(description="ISO month, e.g. 2025-01")] = None,
) -> Response:
    all_rows = STORE.rows(SYSTEM)
    rows = filter_by_month(all_rows, month)
    # Header stays stable even when the filter matches nothing.
    fields = list(all_rows[0]) if all_rows else []

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(fields)
    for row in rows:
        writer.writerow(["" if row.get(field) is None else str(row.get(field)) for field in fields])
    return Response(content=buffer.getvalue(), media_type="text/csv")

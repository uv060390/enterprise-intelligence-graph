"""Mock ops-workflow API.

Dialect: no auth at all; 1-based page/per_page pagination that reports ``total_pages``
instead of a row count, so a client has to walk pages until one comes back empty.
"""

from __future__ import annotations

import math
from typing import Annotated, Any

from fastapi import FastAPI, Query

from mocks.common import STORE, add_common_routes

SYSTEM = "ops_workflow"

app = FastAPI(
    title="mock ops-workflow API",
    description="Synthetic ops-workflow system: unauthenticated, page/per_page pagination.",
)
add_common_routes(app, SYSTEM)


@app.get("/requests")
def list_requests(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    rows = STORE.rows(SYSTEM)
    start = (page - 1) * per_page
    return {
        "items": rows[start : start + per_page],
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(len(rows) / per_page),
    }

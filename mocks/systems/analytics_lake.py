"""Mock analytics-lake API.

Dialect: no auth, no envelope, no pagination — it streams the whole (optionally
month-filtered) export as newline-delimited JSON, the way a lake export actually
behaves. Clients must parse line by line rather than json-decoding a body.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from mocks.common import STORE, add_common_routes, filter_by_month

SYSTEM = "analytics_lake"

app = FastAPI(
    title="mock analytics-lake API",
    description="Synthetic analytics lake: NDJSON streaming export, no envelope.",
)
add_common_routes(app, SYSTEM)


@app.get("/export")
def export(
    month: Annotated[str | None, Query(description="ISO month, e.g. 2025-03")] = None,
) -> StreamingResponse:
    rows = filter_by_month(STORE.rows(SYSTEM), month)

    def lines() -> Iterator[str]:
        for row in rows:
            yield json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")

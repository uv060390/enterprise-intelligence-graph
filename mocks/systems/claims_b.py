"""Mock claims platform B API.

Dialect: no auth, but a legacy mainframe-era contract — camelCase operation name
(``claimExport``), ``pageSize``/``startIndex`` paging, a nested ``resultSet`` envelope
and ``YYYYMM`` service months. Same facts as claims-A, told a different way.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Query

from mocks.common import STORE, add_common_routes, filter_by_month

SYSTEM = "claims_b"

app = FastAPI(
    title="mock claims-B API",
    description="Synthetic claims platform B: legacy resultSet envelope, YYYYMM months.",
)
add_common_routes(app, SYSTEM)


@app.get("/claimExport")
def claim_export(
    pageSize: Annotated[int, Query(ge=1, le=1000)] = 200,  # noqa: N803 — legacy contract
    startIndex: Annotated[int, Query(ge=0)] = 0,  # noqa: N803 — legacy contract
    svc_month: Annotated[str | None, Query(description="ITS month, e.g. 202501")] = None,
) -> dict[str, Any]:
    rows = filter_by_month(STORE.rows(SYSTEM), svc_month, field="svc_month")
    return {
        "resultSet": {
            "rows": rows[startIndex : startIndex + pageSize],
            "rowCount": len(rows),
            "startIndex": startIndex,
        }
    }

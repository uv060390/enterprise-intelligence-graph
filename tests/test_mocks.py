"""Phase 2 contract tests — each mock system's dialect, auth, and pagination.

Every paginated walk must recover exactly the extract's record count; auth systems
must 401 without credentials; quirk formats (legacy envelope, NDJSON, CSV,
required-param) must hold. Tests run against the in-process app; extracts
auto-generate on first startup if missing.
"""

import base64
import csv
import io
import json

import pytest
from starlette.testclient import TestClient

from mocks.app import app
from pipeline.schemas import SYSTEMS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def inventory(client):
    counts = {}
    for system in SYSTEMS:
        body = client.get(f"/{system}/_inventory").json()
        assert body["system"] == system
        assert body["record_count"] > 0
        assert body["fields"] == sorted(body["fields"])
        counts[system] = body["record_count"]
    return counts


def test_health_endpoints(client):
    for system in SYSTEMS:
        body = client.get(f"/{system}/health").json()
        assert body["status"] == "ok" and body["system"] == system


# ------------------------------------------------------------------- ticketing


def test_ticketing_requires_api_key(client):
    assert client.get("/ticketing/tickets").status_code == 401
    assert client.get("/ticketing/tickets", headers={"X-Api-Key": "wrong"}).status_code == 401


def test_ticketing_offset_pagination_recovers_all(client, inventory):
    headers = {"X-Api-Key": "ticketing-dev-key"}
    seen, offset = [], 0
    while True:
        body = client.get(f"/ticketing/tickets?offset={offset}&limit=100", headers=headers).json()
        assert body["total"] == inventory["ticketing"]
        if not body["tickets"]:
            break
        seen.extend(t["ticket_id"] for t in body["tickets"])
        offset += len(body["tickets"])
    assert len(seen) == len(set(seen)) == inventory["ticketing"]


def test_ticketing_limit_cap(client):
    headers = {"X-Api-Key": "ticketing-dev-key"}
    assert client.get("/ticketing/tickets?limit=101", headers=headers).status_code == 422


# ---------------------------------------------------------------- ops_workflow


def test_ops_page_pagination(client, inventory):
    first = client.get("/ops_workflow/requests?page=1&per_page=25").json()
    total_pages = first["total_pages"]
    seen = []
    for page in range(1, total_pages + 1):
        body = client.get(f"/ops_workflow/requests?page={page}&per_page=25").json()
        seen.extend(r["request_id"] for r in body["items"])
    assert len(seen) == len(set(seen)) == inventory["ops_workflow"]
    beyond = client.get(f"/ops_workflow/requests?page={total_pages + 5}&per_page=25").json()
    assert beyond["items"] == [] and beyond["total_pages"] == total_pages


# ------------------------------------------------------------------------ crm


def test_crm_bearer_auth(client):
    assert client.get("/crm/accounts").status_code == 401


def test_crm_cursor_walk(client, inventory):
    headers = {"Authorization": "Bearer crm-dev-token"}
    seen, cursor = [], None
    while True:
        url = "/crm/accounts?batch=50" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url, headers=headers).json()
        seen.extend(r["account_id"] for r in body["records"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == inventory["crm"]


def test_crm_invalid_cursor_400(client):
    headers = {"Authorization": "Bearer crm-dev-token"}
    bad = base64.b64encode(b"not-an-index").decode()
    assert client.get(f"/crm/accounts?cursor={bad}", headers=headers).status_code == 400


# --------------------------------------------------------------------- claims


def test_claims_a_month_filter_partitions(client, inventory):
    total = 0
    for month_num in range(1, 13):
        month = f"2025-{month_num:02d}"
        body = client.get(f"/claims_a/claims?limit=1&month={month}").json()
        total += body["total"]
    assert total == inventory["claims_a"]


def test_claims_b_legacy_envelope_and_month_format(client, inventory):
    body = client.get("/claims_b/claimExport?pageSize=5&startIndex=0").json()
    rows = body["resultSet"]["rows"]
    assert body["resultSet"]["rowCount"] == inventory["claims_b"]
    assert body["resultSet"]["startIndex"] == 0
    assert len(rows) == 5
    assert rows[0]["svc_month"].isdigit() and len(rows[0]["svc_month"]) == 6
    filtered = client.get("/claims_b/claimExport?pageSize=1&svc_month=202503").json()
    assert 0 < filtered["resultSet"]["rowCount"] < inventory["claims_b"]


# --------------------------------------------------------------- credentialing


def test_credentialing_requires_as_of(client, inventory):
    assert client.get("/credentialing/records").status_code == 400
    body = client.get("/credentialing/records?as_of=2026-01-01").json()
    assert len(body["records"]) == inventory["credentialing"]
    assert body["as_of"] == "2026-01-01"


# -------------------------------------------------------------- analytics_lake


def test_analytics_streams_ndjson(client, inventory):
    resp = client.get("/analytics_lake/export")
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in resp.text.strip().splitlines()]
    assert len(lines) == inventory["analytics_lake"]
    assert "npi" in lines[0]


# ---------------------------------------------------------------- finance_mart


def test_finance_basic_auth_and_csv(client, inventory):
    assert client.get("/finance_mart/payments.csv").status_code == 401
    resp = client.get("/finance_mart/payments.csv", auth=("finance", "finance-dev"))
    assert resp.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == inventory["finance_mart"]
    assert "tin" in rows[0] and "paid_total" in rows[0]
    one_month = client.get(
        "/finance_mart/payments.csv?month=2025-01", auth=("finance", "finance-dev")
    )
    month_rows = list(csv.DictReader(io.StringIO(one_month.text)))
    assert 0 < len(month_rows) < len(rows)

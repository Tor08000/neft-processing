from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.api.dependencies.admin import require_admin_user
from app.models.external_request_log import ExternalRequestLog
from app.models.partner import Partner
from app.routers.admin import integration_monitoring
from app.services.integration_monitoring import (
    azs_stats,
    log_external_request,
    partner_status_summary,
)
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


INTEGRATION_MONITORING_TEST_TABLES = (
    Partner.__table__,
    ExternalRequestLog.__table__,
)


def _admin_integration_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_admin_user)])
    router.include_router(integration_monitoring.router)
    return router


@pytest.fixture
def db():
    with scoped_session_context(tables=INTEGRATION_MONITORING_TEST_TABLES) as session:
        yield session


@pytest.fixture
def partner(db):
    partner = Partner(
        id=str(uuid4()),
        name="Partner 1",
        type="AZS",
        code="PARTNER-1",
        legal_name="Partner 1 LLC",
        partner_type="OTHER",
        token="t",
        allowed_ips=[],
        status="ACTIVE",
        contacts={},
    )
    db.add(partner)
    db.commit()
    return partner


def _seed_logs(db, partner_id: str):
    now = datetime.now(timezone.utc)
    log_external_request(
        db,
        partner_id=partner_id,
        azs_id="azs-1",
        terminal_id="t1",
        operation_id="op-1",
        request_type="AUTHORIZE",
        amount=100,
        liters=10.0,
        currency="RUB",
        status="APPROVED",
        reason_category=None,
        risk_code=None,
        limit_code=None,
        latency_ms=120,
    )
    past_time = now - timedelta(minutes=1)
    old = log_external_request(
        db,
        partner_id=partner_id,
        azs_id="azs-2",
        terminal_id="t2",
        operation_id="op-2",
        request_type="AUTHORIZE",
        amount=50,
        liters=5.0,
        currency="RUB",
        status="DECLINED",
        reason_category="RISK",
        risk_code="BLOCK",
        limit_code=None,
        latency_ms=500,
    )
    old.created_at = past_time
    db.add(old)
    db.commit()


def test_partner_status_summary(db, partner):
    _seed_logs(db, partner.id)
    summary = partner_status_summary(db, window_minutes=5)
    assert summary
    entry = summary[0]
    assert entry["partner_id"] == partner.id
    assert entry["total_requests"] == 2
    assert entry["status"] in {"ONLINE", "DEGRADED"}


def test_azs_stats(db, partner):
    _seed_logs(db, partner.id)
    stats = azs_stats(db, window_minutes=5, partner_id=partner.id)
    assert len(stats) == 2
    azs1 = next(item for item in stats if item["azs_id"] == "azs-1")
    assert azs1["declines_total"] == 0
    azs2 = next(item for item in stats if item["azs_id"] == "azs-2")
    assert azs2["declines_total"] == 1
    assert azs2["declines_by_category"]["RISK"] == 1


@pytest.fixture
def api_client(db):
    with router_client_context(
        router=_admin_integration_router(),
        prefix="/api/v1/admin",
        db_session=db,
        dependency_overrides={require_admin_user: lambda: {"roles": ["ADMIN"]}},
    ) as client:
        yield client


def test_admin_endpoints(api_client: TestClient, db, partner):
    _seed_logs(db, partner.id)

    resp = api_client.get("/api/v1/admin/integration/partners/status")
    assert resp.status_code == 200
    assert resp.json()["items"]

    resp = api_client.get("/api/v1/admin/integration/azs/heatmap", params={"partner_id": partner.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["azs_id"]

    resp = api_client.get(
        "/api/v1/admin/integration/requests",
        params={"partner_id": partner.id, "status": "DECLINED", "limit": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["status"]

    since = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    resp = api_client.get(
        "/api/v1/admin/integration/declines/recent",
        params={"since": since, "partner_id": partner.id},
    )
    assert resp.status_code == 200
    feed = resp.json()
    assert feed["items"]

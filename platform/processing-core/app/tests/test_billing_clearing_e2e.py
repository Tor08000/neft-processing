import os
from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DISABLE_CELERY", "1")

from app.api.dependencies.admin import require_admin_user
from app.api.routes import transactions as transactions_api
from app.api.v1.endpoints import reports_billing as reports_billing_endpoint
from app.db import get_db
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing
from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation
from app.models.operation import Operation
from app.routers.admin.billing import router as admin_billing_router
from app.routers.admin.clearing import router as admin_clearing_router
from app.security.rbac.principal import get_principal
from app.services import limits as limits_service
from app.services.limits import CheckAndReserveResult
from app.tests._money_router_harness import FUEL_STATIONS_REFLECTED, admin_principal_override, admin_token_override


BILLING_CLEARING_E2E_TEST_TABLES = (
    FUEL_STATIONS_REFLECTED,
    Operation.__table__,
    BillingPeriod.__table__,
    BillingSummary.__table__,
    Clearing.__table__,
    BillingJobRun.__table__,
    ClearingBatch.__table__,
    ClearingBatchOperation.__table__,
)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    for table in BILLING_CLEARING_E2E_TEST_TABLES:
        table.create(bind=engine, checkfirst=True)
    try:
        yield SessionLocal
    finally:
        for table in reversed(BILLING_CLEARING_E2E_TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture()
def api_client(session_factory):
    app = FastAPI()
    app.include_router(transactions_api.router, prefix="/api/v1")
    app.include_router(reports_billing_endpoint.router)
    app.include_router(admin_billing_router, prefix="/api/v1/admin")
    app.include_router(admin_clearing_router, prefix="/api/v1/admin")

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def approved_limits(*_args, **_kwargs) -> CheckAndReserveResult:
        return CheckAndReserveResult(
            approved=True,
            response_code="00",
            response_message="OK",
            daily_limit=1_000_000,
            limit_per_tx=50_000,
            used_today=0,
            new_used_today=0,
            applied_rule_id=None,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = admin_principal_override
    app.dependency_overrides[require_admin_user] = admin_token_override

    original_get_sessionmaker = transactions_api.get_sessionmaker
    original_limits_check = transactions_api.call_limits_check_and_reserve_sync
    transactions_api._TRANSACTIONS.clear()
    transactions_api.get_sessionmaker = lambda: session_factory
    transactions_api.call_limits_check_and_reserve_sync = approved_limits

    try:
        with TestClient(app) as client:
            yield client
    finally:
        transactions_api._TRANSACTIONS.clear()
        transactions_api.get_sessionmaker = original_get_sessionmaker
        transactions_api.call_limits_check_and_reserve_sync = original_limits_check


def test_billing_and_clearing_pipeline(api_client: TestClient, admin_auth_headers):
    limits_service.celery_app = None
    auth_resp = api_client.post(
        "/api/v1/processing/terminal-auth",
        json={
            "merchant_id": "m-1",
            "terminal_id": "t-1",
            "client_id": "c-1",
            "card_id": "card-1",
            "amount": 1500,
            "currency": "RUB",
        },
    )
    assert auth_resp.status_code == 200
    auth_id = auth_resp.json()["operation_id"]

    capture_resp = api_client.post(
        f"/api/v1/transactions/{auth_id}/capture",
        json={"amount": 1500},
    )
    assert capture_resp.status_code == 200
    capture_payload = capture_resp.json()
    capture_id = capture_payload["operation_id"]
    operation_day = datetime.fromisoformat(capture_payload["created_at"]).date()

    summary_resp = api_client.post(
        "/api/v1/reports/billing/summary/rebuild",
        params={
            "date_from": operation_day.isoformat(),
            "date_to": operation_day.isoformat(),
            "merchant_id": "m-1",
        },
        headers=admin_auth_headers,
    )
    assert summary_resp.status_code == 200
    summaries = summary_resp.json()
    assert len(summaries) == 1
    assert summaries[0]["total_captured_amount"] == 1500
    assert summaries[0]["operations_count"] == 1

    admin_summary = api_client.get(
        "/api/v1/admin/billing/summary",
        params={
            "date_from": operation_day.isoformat(),
            "date_to": operation_day.isoformat(),
            "limit": 10,
            "offset": 0,
        },
        headers=admin_auth_headers,
    )
    assert admin_summary.status_code == 200
    assert admin_summary.json()["total"] == 1
    assert len(admin_summary.json()["items"]) == 1

    batch_resp = api_client.post(
        "/api/v1/admin/clearing/batches/build",
        json={
            "date_from": operation_day.isoformat(),
            "date_to": operation_day.isoformat(),
            "merchant_id": "m-1",
        },
        headers=admin_auth_headers,
    )
    assert batch_resp.status_code == 200
    batch = batch_resp.json()
    assert batch["operations_count"] == 1
    assert batch["total_amount"] == 1500

    operations_resp = api_client.get(
        f"/api/v1/admin/clearing/batches/{batch['id']}/operations",
        headers=admin_auth_headers,
    )
    assert operations_resp.status_code == 200
    batch_operations = operations_resp.json()
    assert len(batch_operations) == 1
    assert batch_operations[0]["operation_id"] == capture_id

    start = datetime.combine(operation_day, datetime.min.time())
    end = datetime.combine(operation_day, datetime.max.time())
    turnover_resp = api_client.get(
        "/api/v1/reports/turnover",
        params={
            "group_by": "merchant",
            "from": start.isoformat(),
            "to": end.isoformat(),
            "merchant_id": "m-1",
        },
    )
    assert turnover_resp.status_code == 200
    turnover = turnover_resp.json()
    assert turnover["totals"]["captured_amount"] == 1500
    assert turnover["items"][0]["group_key"]["merchant_id"] == "m-1"

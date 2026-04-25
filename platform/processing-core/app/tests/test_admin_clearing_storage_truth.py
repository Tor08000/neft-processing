from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, MetaData, Numeric, String, Table
from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.clearing import Clearing
from app.services.clearing_service import run_admin_clearing

from ._money_router_harness import admin_clearing_client_context, money_session_context


_LIVE_BILLING_SUMMARY_METADATA = MetaData()

BILLING_SUMMARY_LIVE_SHAPE = Table(
    "billing_summary",
    _LIVE_BILLING_SUMMARY_METADATA,
    Column("id", String(36), primary_key=True),
    Column("billing_date", Date, nullable=False),
    Column("merchant_id", String(64), nullable=False),
    Column("total_amount", BigInteger, nullable=False),
    Column("operations_count", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=True),
    Column("client_id", String(64), nullable=True),
    Column("product_type", String(32), nullable=True),
    Column("currency", String(3), nullable=True),
    Column("total_quantity", Numeric(18, 3), nullable=True),
    Column("commission_amount", BigInteger, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
    Column("status", String(32), nullable=True),
    Column("finalized_at", DateTime(timezone=True), nullable=True),
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=(BILLING_SUMMARY_LIVE_SHAPE, Clearing.__table__, BillingJobRun.__table__)) as db:
        yield db


@pytest.fixture
def admin_client(session: Session) -> TestClient:
    with admin_clearing_client_context(db_session=session) as api_client:
        yield api_client


def test_admin_clearing_accepts_live_billing_summary_storage_shape(admin_client: TestClient, session: Session):
    target_date = date(2099, 12, 1)
    now = datetime.now(timezone.utc)
    session.execute(
        BILLING_SUMMARY_LIVE_SHAPE.insert(),
        [
            {
                "id": "live-shape-summary-1",
                "billing_date": target_date,
                "client_id": "client-1",
                "merchant_id": "merchant-1",
                "product_type": "AI92",
                "currency": "RUB",
                "total_amount": 500,
                "operations_count": 2,
                "commission_amount": 0,
                "status": "FINALIZED",
                "finalized_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "live-shape-summary-2",
                "billing_date": target_date,
                "client_id": "client-2",
                "merchant_id": "merchant-1",
                "product_type": "AI95",
                "currency": "RUB",
                "total_amount": 700,
                "operations_count": 1,
                "commission_amount": 0,
                "status": "FINALIZED",
                "finalized_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "live-shape-summary-3",
                "billing_date": target_date,
                "client_id": "client-3",
                "merchant_id": "merchant-2",
                "product_type": "AI95",
                "currency": "USD",
                "total_amount": 900,
                "operations_count": 1,
                "commission_amount": 0,
                "status": "FINALIZED",
                "finalized_at": now,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    session.commit()

    response = admin_client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"clearing_date": target_date.isoformat(), "created": 2}

    stored_batches = session.query(Clearing).filter(Clearing.batch_date == target_date).all()
    assert len(stored_batches) == 2
    assert {(item.merchant_id, item.currency, item.total_amount) for item in stored_batches} == {
        ("merchant-1", "RUB", 1200),
        ("merchant-2", "USD", 900),
    }

    job_runs = session.query(BillingJobRun).filter(BillingJobRun.job_type == BillingJobType.CLEARING).all()
    assert len(job_runs) == 1
    assert job_runs[0].status == BillingJobStatus.SUCCESS
    assert job_runs[0].metrics == {"created": 2}


def test_legacy_admin_clearing_helper_accepts_live_billing_summary_storage_shape(session: Session):
    target_date = date(2099, 12, 2)
    now = datetime.now(timezone.utc)
    session.execute(
        BILLING_SUMMARY_LIVE_SHAPE.insert(),
        [
            {
                "id": "legacy-live-shape-summary-1",
                "billing_date": target_date,
                "client_id": "client-4",
                "merchant_id": "merchant-legacy",
                "product_type": "AI92",
                "currency": "RUB",
                "total_amount": 400,
                "operations_count": 1,
                "commission_amount": 0,
                "status": "FINALIZED",
                "finalized_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "legacy-live-shape-summary-2",
                "billing_date": target_date,
                "client_id": "client-5",
                "merchant_id": "merchant-legacy",
                "product_type": "AI95",
                "currency": "RUB",
                "total_amount": 600,
                "operations_count": 1,
                "commission_amount": 0,
                "status": "FINALIZED",
                "finalized_at": now,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    session.commit()

    result = run_admin_clearing(session, clearing_date=target_date)

    assert result == {"created": 1}
    stored_batch = session.query(Clearing).filter(Clearing.batch_date == target_date).one()
    assert stored_batch.merchant_id == "merchant-legacy"
    assert stored_batch.total_amount == 1000

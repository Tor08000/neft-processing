from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal
from app.main import app
from app.models.billing_job_run import BillingJobRun, BillingJobType
from app.models.billing_period import BillingPeriod
from app.models.billing_summary import BillingSummary
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.services.clearing_runs import ClearingRunInProgress, ClearingRunService
from app.services.demo_seed import DemoSeeder, DEMO_CLIENT_ID
from app.services.finance import FinanceOperationInProgress, FinanceService


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_period(day: date) -> tuple[str, str]:
    start_at = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    return start_at.isoformat(), end_at.isoformat()


def _require_db(session):
    try:
        session.execute(text("select 1"))
    except OperationalError:
        pytest.skip("Database unavailable for idempotency flow tests")


def test_manual_billing_idempotent_key_reuses_job(admin_client: TestClient, session):
    _require_db(session)
    billing_date = date(2024, 1, 5)
    DemoSeeder(session).seed(billing_date=billing_date)
    start_at, end_at = _make_period(billing_date)

    payload = {
        "period_type": "ADHOC",
        "start_at": start_at,
        "end_at": end_at,
        "tz": "UTC",
        "client_id": None,
        "idempotency_key": "idem-billing-manual",
    }

    first = admin_client.post("/api/v1/admin/billing/run", json=payload)
    assert first.status_code == 200
    second = admin_client.post("/api/v1/admin/billing/run", json=payload)
    assert second.status_code == 200

    runs = (
        session.query(BillingJobRun)
        .filter(BillingJobRun.job_type == BillingJobType.MANUAL_RUN)
        .filter(BillingJobRun.correlation_id == "idem-billing-manual")
        .all()
    )
    assert len(runs) == 1


def test_clearing_run_reuses_existing_result(session):
    _require_db(session)
    billing_date = date(2024, 1, 6)
    DemoSeeder(session).seed(billing_date=billing_date)
    job_key = "idem-clearing"
    service = ClearingRunService(session)

    first = asyncio.run(service.run(clearing_date=billing_date, idempotency_key=job_key))
    assert first
    second = asyncio.run(service.run(clearing_date=billing_date, idempotency_key=job_key))
    assert len(second) == len(first)

    runs = (
        session.query(BillingJobRun)
        .filter(BillingJobRun.job_type == BillingJobType.CLEARING_RUN)
        .filter(BillingJobRun.correlation_id == job_key)
        .all()
    )
    assert len(runs) == 1


def test_finance_payment_and_credit_note_idempotent(session):
    _require_db(session)
    billing_date = date(2024, 1, 7)
    DemoSeeder(session).seed(billing_date=billing_date)
    invoice = session.query(Invoice).filter(Invoice.client_id == DEMO_CLIENT_ID).first()
    assert invoice is not None
    invoice.status = InvoiceStatus.SENT
    invoice.pdf_status = InvoicePdfStatus.READY
    session.add(invoice)
    session.commit()

    finance = FinanceService(session)
    payment_key = "idem-payment"
    payment = finance.apply_payment(invoice_id=invoice.id, amount=100, currency="RUB", idempotency_key=payment_key)
    payment_repeat = finance.apply_payment(invoice_id=invoice.id, amount=100, currency="RUB", idempotency_key=payment_key)
    assert payment.payment.id == payment_repeat.payment.id

    credit_key = "idem-credit"
    credit = finance.create_credit_note(
        invoice_id=invoice.id,
        amount=50,
        currency="RUB",
        reason="test",
        idempotency_key=credit_key,
    )
    credit_repeat = finance.create_credit_note(
        invoice_id=invoice.id,
        amount=50,
        currency="RUB",
        reason="test",
        idempotency_key=credit_key,
    )
    assert credit.credit_note.id == credit_repeat.credit_note.id
    assert credit_repeat.invoice.amount_due == credit.invoice.amount_due


def test_seed_endpoint_returns_period(admin_client: TestClient):
    with SessionLocal() as db:
        _require_db(db)
    resp = admin_client.post("/api/v1/admin/billing/seed")
    assert resp.status_code == 200
    payload = resp.json()
    assert "billing_period_id" in payload
    assert "period_from" in payload

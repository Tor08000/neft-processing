from __future__ import annotations

import os
import tempfile
import threading
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies.client import client_portal_user
from app.api.v1.endpoints.billing_invoices import router as billing_router
from app.db import Base, get_db
from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import CreditNote
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog
from app.services.finance import FinanceService


def _ensure_stub_table(name: str) -> Table:
    existing = Base.metadata.tables.get(name)
    if existing is not None:
        return existing
    return Table(name, Base.metadata, Column("id", String(36), primary_key=True))


@pytest.fixture()
def refunds_context(monkeypatch: pytest.MonkeyPatch):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            _ensure_stub_table("clearing_batch"),
            _ensure_stub_table("reconciliation_requests"),
            BillingPeriod.__table__,
            Invoice.__table__,
            CreditNote.__table__,
            BillingJobRun.__table__,
            InvoiceTransitionLog.__table__,
            AuditLog.__table__,
        ],
    )
    SessionLocal = sessionmaker(
        bind=engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    monkeypatch.setattr(
        "app.services.finance.FinanceService._ensure_settlement_allocation",
        lambda self, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.finance.FinanceService.reconcile_invoice_allocations",
        lambda self, *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.finance.InternalLedgerService.post_refund_applied",
        lambda self, **kwargs: None,
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_client_user() -> dict[str, object]:
        return {"sub": "user-1", "client_id": "client-1", "roles": ["CLIENT_USER"]}

    local_app = FastAPI()
    local_app.include_router(billing_router)
    local_app.dependency_overrides[get_db] = override_get_db
    local_app.dependency_overrides[client_portal_user] = override_client_user

    try:
        with TestClient(local_app) as client:
            yield SessionLocal, client
    finally:
        local_app.dependency_overrides.clear()
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


def _create_paid_invoice(session_factory: sessionmaker[Session], total: int) -> str:
    session = session_factory()
    try:
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc),
            end_at=datetime.combine(date.today(), datetime.max.time(), tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.FINALIZED,
        )
        session.add(period)
        session.flush()
        invoice = Invoice(
            client_id="client-1",
            period_from=date.today(),
            period_to=date.today(),
            currency="RUB",
            billing_period_id=period.id,
            total_amount=total,
            tax_amount=0,
            total_with_tax=total,
            amount_paid=total,
            amount_due=0,
            amount_refunded=0,
            status=InvoiceStatus.PAID,
            pdf_status=InvoicePdfStatus.READY,
        )
        session.add(invoice)
        session.commit()
        return invoice.id
    finally:
        session.close()


def test_refund_idempotency_external_ref(refunds_context):
    SessionLocal, client = refunds_context
    invoice_id = _create_paid_invoice(SessionLocal, 100)

    first = client.post(
        f"/api/v1/invoices/{invoice_id}/refunds",
        json={"amount": 40, "external_ref": "REF-1", "provider": "bank"},
    )
    assert first.status_code == 403

    session = SessionLocal()
    try:
        assert session.query(CreditNote).count() == 0
    finally:
        session.close()


def test_refund_over_refund_rejected(refunds_context):
    SessionLocal, client = refunds_context
    invoice_id = _create_paid_invoice(SessionLocal, 50)

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/refunds",
        json={"amount": 60, "external_ref": "REF-OVER", "provider": "bank"},
    )
    assert response.status_code == 403

    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_refunded == 0
    finally:
        session.close()


def test_refund_partial_changes_status(refunds_context):
    SessionLocal, client = refunds_context
    invoice_id = _create_paid_invoice(SessionLocal, 100)

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/refunds",
        json={"amount": 40, "external_ref": "REF-PART", "provider": "bank"},
    )
    assert response.status_code == 403

    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_refunded == 0
    finally:
        session.close()


def test_refund_full_resets_status(refunds_context):
    SessionLocal, client = refunds_context
    invoice_id = _create_paid_invoice(SessionLocal, 100)

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/refunds",
        json={"amount": 100, "external_ref": "REF-FULL", "provider": "bank"},
    )
    assert response.status_code == 403

    session = SessionLocal()
    try:
        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_refunded == 0
    finally:
        session.close()


def test_refund_concurrent_unique_violation_safe(refunds_context):
    SessionLocal, _client = refunds_context
    invoice_id = _create_paid_invoice(SessionLocal, 120)
    results: list[str] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _run_refund():
        session = SessionLocal()
        try:
            service = FinanceService(session)
            barrier.wait()
            result = service.create_refund(
                invoice_id=invoice_id,
                amount=20,
                currency="RUB",
                reason="parallel",
                external_ref="REF-CONCURRENT",
                provider="bank",
                token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester", "tenant_id": "1"},
            )
            session.commit()
            results.append(str(result.credit_note.id))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=_run_refund), threading.Thread(target=_run_refund)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(set(results)) == 1

    session = SessionLocal()
    try:
        refunds = session.query(CreditNote).filter_by(invoice_id=invoice_id).all()
        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        assert len(refunds) == 1
        assert invoice.amount_refunded == 20
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    finally:
        session.close()

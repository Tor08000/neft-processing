from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog

from ._money_router_harness import (
    ADMIN_BILLING_INVOICE_TEST_TABLES,
    admin_billing_client_context,
    money_session_context,
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=ADMIN_BILLING_INVOICE_TEST_TABLES) as db:
        yield db


@pytest.fixture
def admin_client(session: Session) -> TestClient:
    with admin_billing_client_context(db_session=session) as api_client:
        yield api_client


def _make_invoice(*, invoice_id: str, client_id: str, status: InvoiceStatus, pdf_status: InvoicePdfStatus) -> Invoice:
    return Invoice(
        id=invoice_id,
        client_id=client_id,
        period_from=date(2024, 1, 1),
        period_to=date(2024, 1, 31),
        currency="RUB",
        total_amount=1000,
        tax_amount=0,
        total_with_tax=1000,
        amount_paid=0,
        amount_due=1000,
        status=status,
        pdf_status=pdf_status,
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )


def test_admin_invoice_transition_endpoint(admin_client: TestClient, session: Session) -> None:
    invoice = _make_invoice(
        invoice_id="inv-transition",
        client_id="client-transition",
        status=InvoiceStatus.ISSUED,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.commit()

    response = admin_client.post(
        f"/api/v1/admin/billing/invoices/{invoice.id}/transition",
        json={
            "to": InvoiceStatus.SENT.value,
            "reason": "pdf ready",
            "metadata": {"ticket": "SUP-123"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == InvoiceStatus.SENT.value
    assert body["sent_at"] is not None

    stored = session.query(Invoice).filter(Invoice.id == invoice.id).one()
    assert stored.status == InvoiceStatus.SENT

    transition_logs = session.query(InvoiceTransitionLog).filter(InvoiceTransitionLog.invoice_id == invoice.id).all()
    assert len(transition_logs) == 1
    assert transition_logs[0].from_status == InvoiceStatus.ISSUED
    assert transition_logs[0].to_status == InvoiceStatus.SENT
    assert transition_logs[0].reason == "pdf ready"
    assert transition_logs[0].metadata_json == {"ticket": "SUP-123"}

    audit_logs = session.query(AuditLog).filter(AuditLog.entity_type == "invoice", AuditLog.entity_id == invoice.id).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].event_type == "INVOICE_STATUS_CHANGED"
    assert audit_logs[0].action == "UPDATE_STATE"

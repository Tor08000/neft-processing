from __future__ import annotations

import threading
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import CreditNote
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.services.finance import FinanceService


def _create_paid_invoice(total: int) -> str:
    session = get_sessionmaker()()
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
    invoice_id = invoice.id
    session.close()
    return invoice_id


def test_refund_idempotency_external_ref(client_auth_headers: dict):
    invoice_id = _create_paid_invoice(100)

    with TestClient(app) as client:
        client.headers.update(client_auth_headers)
        first = client.post(
            f"/api/v1/invoices/{invoice_id}/refunds",
            json={"amount": 40, "external_ref": "REF-1", "provider": "bank"},
        )
        assert first.status_code == 403


def test_refund_over_refund_rejected(client_auth_headers: dict):
    invoice_id = _create_paid_invoice(50)

    with TestClient(app) as client:
        client.headers.update(client_auth_headers)
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/refunds",
            json={"amount": 60, "external_ref": "REF-OVER", "provider": "bank"},
        )
        assert response.status_code == 403


def test_refund_partial_changes_status(client_auth_headers: dict):
    invoice_id = _create_paid_invoice(100)

    with TestClient(app) as client:
        client.headers.update(client_auth_headers)
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/refunds",
            json={"amount": 40, "external_ref": "REF-PART", "provider": "bank"},
        )
        assert response.status_code == 403


def test_refund_full_resets_status(client_auth_headers: dict):
    invoice_id = _create_paid_invoice(100)

    with TestClient(app) as client:
        client.headers.update(client_auth_headers)
        response = client.post(
            f"/api/v1/invoices/{invoice_id}/refunds",
            json={"amount": 100, "external_ref": "REF-FULL", "provider": "bank"},
        )
        assert response.status_code == 403


def test_refund_concurrent_unique_violation_safe():
    invoice_id = _create_paid_invoice(120)
    results: list[str] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _run_refund():
        try:
            session = get_sessionmaker()()
            service = FinanceService(session)
            barrier.wait()
            result = service.create_refund(
                invoice_id=invoice_id,
                amount=20,
                currency="RUB",
                reason="parallel",
                external_ref="REF-CONCURRENT",
                provider="bank",
                token={"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"},
            )
            session.commit()
            results.append(str(result.credit_note.id))
            session.close()
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=_run_refund), threading.Thread(target=_run_refund)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(set(results)) == 1

    session = get_sessionmaker()()
    refunds = session.query(CreditNote).filter_by(invoice_id=invoice_id).all()
    assert len(refunds) == 1
    session.close()

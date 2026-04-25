from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.contract_limits import TariffPlan
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


def _make_invoice(
    *,
    invoice_id: str,
    client_id: str,
    period_from: date,
    period_to: date,
    status: InvoiceStatus,
    created_at: datetime,
    pdf_status: InvoicePdfStatus = InvoicePdfStatus.NONE,
) -> Invoice:
    total_amount = 1500 if invoice_id.endswith("issued") else 1000
    return Invoice(
        id=invoice_id,
        client_id=client_id,
        period_from=period_from,
        period_to=period_to,
        currency="RUB",
        total_amount=total_amount,
        tax_amount=0,
        total_with_tax=total_amount,
        amount_paid=0,
        amount_due=total_amount,
        status=status,
        pdf_status=pdf_status,
        created_at=created_at,
    )


def test_admin_tariff_price_crud(admin_client: TestClient, session: Session):
    session.add(TariffPlan(id="tariff-api", name="API"))
    session.commit()

    create_resp = admin_client.post(
        "/api/v1/admin/billing/tariffs/tariff-api/prices",
        json={
            "product_id": "prod-1",
            "price_per_liter": "10.5",
            "currency": "RUB",
            "priority": 10,
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["tariff_id"] == "tariff-api"
    assert created["price_per_liter"] == "10.500000"

    price_id = created["id"]
    update_resp = admin_client.post(
        "/api/v1/admin/billing/tariffs/tariff-api/prices",
        json={
            "id": price_id,
            "product_id": "prod-1",
            "price_per_liter": "11.0",
            "currency": "RUB",
        },
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["price_per_liter"] == "11.000000"

    list_resp = admin_client.get("/api/v1/admin/billing/tariffs/tariff-api/prices")
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["price_per_liter"] == "11.000000"


def test_admin_invoice_listing_filters(admin_client: TestClient, session: Session):
    period_from = date(2024, 5, 1)
    period_to = date(2024, 5, 31)

    issued = _make_invoice(
        invoice_id="inv-issued",
        client_id="client-1",
        period_from=period_from,
        period_to=period_to,
        status=InvoiceStatus.ISSUED,
        created_at=datetime(2024, 5, 31, 12, 0, tzinfo=timezone.utc),
    )
    draft = _make_invoice(
        invoice_id="inv-draft",
        client_id="client-2",
        period_from=period_from,
        period_to=period_to,
        status=InvoiceStatus.DRAFT,
        created_at=datetime(2024, 5, 31, 11, 0, tzinfo=timezone.utc),
    )
    session.add_all([issued, draft])
    session.commit()

    response = admin_client.get(
        "/api/v1/admin/billing/invoices",
        params={"status": InvoiceStatus.ISSUED.value},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == issued.id


def test_generate_route_returns_existing_period_invoices_and_status_transition(
    admin_client: TestClient, session: Session
):
    session.add(TariffPlan(id="tariff-main", name="Main"))

    matching_invoice = _make_invoice(
        invoice_id="invoice-issued",
        client_id="client-one",
        period_from=date(2024, 6, 1),
        period_to=date(2024, 6, 30),
        status=InvoiceStatus.ISSUED,
        pdf_status=InvoicePdfStatus.READY,
        created_at=datetime(2024, 6, 5, 12, 0, tzinfo=timezone.utc),
    )
    non_matching_invoice = _make_invoice(
        invoice_id="invoice-draft",
        client_id="client-two",
        period_from=date(2024, 6, 1),
        period_to=date(2024, 6, 30),
        status=InvoiceStatus.DRAFT,
        created_at=datetime(2024, 6, 5, 11, 0, tzinfo=timezone.utc),
    )
    session.add_all([matching_invoice, non_matching_invoice])
    session.commit()

    generate_resp = admin_client.post(
        "/api/v1/admin/billing/invoices/generate",
        json={"period_from": "2024-06-01", "period_to": "2024-06-30"},
    )
    assert generate_resp.status_code == 202
    created_ids = generate_resp.json()["created_ids"]
    assert created_ids == [matching_invoice.id]

    status_resp = admin_client.post(
        f"/api/v1/admin/billing/invoices/{matching_invoice.id}/status",
        json={"status": InvoiceStatus.SENT.value, "reason": "pdf_ready"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == InvoiceStatus.SENT.value

    stored = session.query(Invoice).filter(Invoice.id == matching_invoice.id).one()
    assert stored.status == InvoiceStatus.SENT

    transition_logs = session.query(InvoiceTransitionLog).filter(
        InvoiceTransitionLog.invoice_id == matching_invoice.id
    ).all()
    assert len(transition_logs) == 1
    assert transition_logs[0].to_status == InvoiceStatus.SENT

    audit_logs = session.query(AuditLog).filter(
        AuditLog.entity_type == "invoice",
        AuditLog.entity_id == matching_invoice.id,
    ).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].event_type == "INVOICE_STATUS_CHANGED"

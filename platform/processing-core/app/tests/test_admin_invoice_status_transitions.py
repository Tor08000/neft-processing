from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.invoice import InvoiceStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def test_admin_status_update_success(admin_client: TestClient, session: Session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-1",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            lines=[BillingLineData(product_id="p1", liters=None, unit_price=None, line_amount=500)],
            status=InvoiceStatus.DRAFT,
        )
    )

    response = admin_client.post(
        f"/api/v1/admin/billing/invoices/{invoice.id}/status",
        json={"status": InvoiceStatus.ISSUED.value},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == InvoiceStatus.ISSUED.value
    assert payload["issued_at"] is not None


def test_admin_status_update_forbidden_transition(admin_client: TestClient, session: Session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-2",
            period_from=date(2024, 2, 1),
            period_to=date(2024, 2, 29),
            currency="RUB",
            lines=[BillingLineData(product_id="p2", liters=None, unit_price=None, line_amount=800)],
            status=InvoiceStatus.SENT,
        )
    )
    invoice.amount_paid = 100
    invoice.amount_due = max(invoice.total_with_tax - invoice.amount_paid, 0)
    session.add(invoice)
    session.commit()

    response = admin_client.post(
        f"/api/v1/admin/billing/invoices/{invoice.id}/status",
        json={"status": InvoiceStatus.CANCELLED.value},
    )

    assert response.status_code == 409

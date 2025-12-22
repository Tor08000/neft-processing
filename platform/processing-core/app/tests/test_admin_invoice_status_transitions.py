from datetime import date
import os

import pytest
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import db as app_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.invoice import InvoicePdfStatus, InvoiceStatus  # noqa: E402
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository  # noqa: E402


@pytest.fixture(autouse=True)
def _setup_db():
    engine = app_db.make_engine("sqlite://", schema="")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    app_db._engine = engine
    app_db._SessionLocal = TestingSessionLocal

    app_db.Base.metadata.drop_all(bind=engine)
    app_db.Base.metadata.create_all(bind=engine)
    yield
    app_db.Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = app_db.get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def test_admin_invoice_transition_endpoint(admin_client: TestClient, session) -> None:
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-transition",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            lines=[BillingLineData(product_id="prod-1", liters=None, unit_price=None, line_amount=1000)],
            status=InvoiceStatus.ISSUED,
            pdf_status=InvoicePdfStatus.READY,
        ),
        auto_commit=True,
    )

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

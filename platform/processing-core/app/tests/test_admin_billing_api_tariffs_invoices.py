from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.client import Client
from app.models.contract_limits import TariffPlan
from app.models.invoice import InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
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


def _make_operation(*, client_id: str, created_at: datetime, status: OperationStatus, amount: int) -> Operation:
    return Operation(
        ext_operation_id=f"ext-{created_at.timestamp()}",
        operation_type=OperationType.COMMIT,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        merchant_id="m-1",
        terminal_id="t-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=ProductType.AI92,
        amount=amount,
        currency="RUB",
        quantity=Decimal("10.000"),
        unit_price=Decimal("10.000"),
        captured_amount=0,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
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
    repo = BillingRepository(session)
    period_from = date(2024, 5, 1)
    period_to = date(2024, 5, 31)

    issued = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-1",
            period_from=period_from,
            period_to=period_to,
            currency="RUB",
            lines=[BillingLineData(product_id="prod-1", liters=None, unit_price=None, line_amount=1000)],
            status=InvoiceStatus.ISSUED,
        )
    )
    repo.create_invoice(
        BillingInvoiceData(
            client_id="client-2",
            period_from=period_from,
            period_to=period_to,
            currency="RUB",
            lines=[BillingLineData(product_id="prod-2", liters=None, unit_price=None, line_amount=500)],
            status=InvoiceStatus.DRAFT,
        )
    )

    response = admin_client.get(
        "/api/v1/admin/billing/invoices",
        params={"status": InvoiceStatus.ISSUED.value},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == issued.id


def test_generate_and_change_invoice_status(admin_client: TestClient, session: Session):
    tariff = TariffPlan(id="tariff-main", name="Main")
    session.add(tariff)

    client_id = uuid4()
    client = Client(id=client_id, name="Test", tariff_plan=tariff.id, status="ACTIVE")
    session.add(client)

    op_ts = datetime(2024, 6, 5, 12, 0, 0)
    operation = _make_operation(client_id=str(client_id), created_at=op_ts, status=OperationStatus.COMPLETED, amount=1500)
    session.add(operation)
    session.commit()

    generate_resp = admin_client.post(
        "/api/v1/admin/billing/invoices/generate",
        json={"period_from": "2024-06-01", "period_to": "2024-06-30"},
    )
    assert generate_resp.status_code == 202
    created_ids = generate_resp.json()["created_ids"]
    assert len(created_ids) == 1

    invoice_id = created_ids[0]
    status_resp = admin_client.post(
        f"/api/v1/admin/billing/invoices/{invoice_id}/status",
        json={"status": InvoiceStatus.ISSUED.value},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == InvoiceStatus.ISSUED.value

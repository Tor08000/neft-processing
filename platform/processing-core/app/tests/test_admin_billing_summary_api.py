from datetime import date, datetime, timedelta
from decimal import Decimal
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing_service import build_billing_summary_for_date


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


def _make_operation(
    *,
    created_at: datetime,
    status: OperationStatus,
    client_id: str,
    merchant_id: str,
    product_type: ProductType,
    amount: int,
    currency: str = "RUB",
    quantity: Decimal | None = None,
) -> Operation:
    if status == OperationStatus.COMPLETED:
        op_type = OperationType.COMMIT
    elif status == OperationStatus.REFUNDED:
        op_type = OperationType.REFUND
    elif status == OperationStatus.REVERSED:
        op_type = OperationType.REVERSE
    else:
        op_type = OperationType.AUTH

    return Operation(
        ext_operation_id=f"ext-{created_at.timestamp()}-{status.value}-{client_id}-{merchant_id}",
        operation_type=op_type,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        merchant_id=merchant_id,
        terminal_id="terminal-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=product_type,
        amount=amount,
        currency=currency,
        quantity=quantity,
        unit_price=None,
        captured_amount=0,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_admin_billing_summary_filters(admin_client: TestClient, session: Session):
    billing_date = date(2024, 5, 20)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=8)

    operations = [
        _make_operation(
            created_at=base_ts,
            status=OperationStatus.COMPLETED,
            client_id="c-1",
            merchant_id="m-1",
            product_type=ProductType.DIESEL,
            amount=2_000,
            quantity=Decimal("10.000"),
            currency="RUB",
        ),
        _make_operation(
            created_at=base_ts + timedelta(minutes=5),
            status=OperationStatus.REFUNDED,
            client_id="c-1",
            merchant_id="m-1",
            product_type=ProductType.DIESEL,
            amount=500,
            quantity=Decimal("2.000"),
            currency="RUB",
        ),
        _make_operation(
            created_at=base_ts + timedelta(minutes=10),
            status=OperationStatus.COMPLETED,
            client_id="c-2",
            merchant_id="m-2",
            product_type=ProductType.AI92,
            amount=1_000,
            quantity=None,
            currency="USD",
        ),
    ]

    session.add_all(operations)
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    response = admin_client.get(
        "/api/v1/admin/billing/summary",
        params={
            "date_from": billing_date.isoformat(),
            "date_to": billing_date.isoformat(),
            "merchant_id": "m-1",
            "currency": "RUB",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1

    item = payload["items"][0]
    assert item["billing_date"] == billing_date.isoformat()
    assert item["merchant_id"] == "m-1"
    assert item["client_id"] == "c-1"
    assert item["product_type"] == ProductType.DIESEL.value
    assert item["total_amount"] == 1500
    assert item["total_quantity"] == "8.000"
    assert item["operations_count"] == 2
    assert item["commission_amount"] == 15


def test_admin_billing_summary_pagination(admin_client: TestClient, session: Session):
    billing_date = date(2024, 6, 1)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=7)

    ops = []
    for idx in range(3):
        ops.append(
            _make_operation(
                created_at=base_ts + timedelta(minutes=idx),
                status=OperationStatus.COMPLETED,
                client_id=f"client-{idx}",
                merchant_id="merchant-1",
                product_type=ProductType.AI95,
                amount=1_000 + idx * 100,
                quantity=Decimal("1.000"),
            )
        )

    session.add_all(ops)
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    first_page = admin_client.get(
        "/api/v1/admin/billing/summary",
        params={
            "date_from": billing_date.isoformat(),
            "date_to": billing_date.isoformat(),
            "limit": 2,
            "offset": 0,
        },
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["total"] == 3
    assert len(first_payload["items"]) == 2

    second_page = admin_client.get(
        "/api/v1/admin/billing/summary",
        params={
            "date_from": billing_date.isoformat(),
            "date_to": billing_date.isoformat(),
            "limit": 2,
            "offset": 2,
        },
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] == 3
    assert len(second_payload["items"]) == 1


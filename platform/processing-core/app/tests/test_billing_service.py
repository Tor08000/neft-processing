import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine
from app.models.billing_summary import BillingSummary
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


def _make_operation(
    *,
    created_at: datetime,
    status: OperationStatus,
    client_id: str,
    merchant_id: str,
    product_type: ProductType | None,
    amount: int,
    currency: str = "RUB",
    quantity: Decimal | None = None,
):
    if status == OperationStatus.COMPLETED:
        op_type = OperationType.COMMIT
    elif status == OperationStatus.REFUNDED:
        op_type = OperationType.REFUND
    elif status == OperationStatus.REVERSED:
        op_type = OperationType.REVERSE
    else:
        op_type = OperationType.AUTH

    return Operation(
        ext_operation_id=f"ext-{created_at.timestamp()}-{status.value}",
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


def test_build_billing_summary_for_date_creates_summary(session):
    billing_date = date(2024, 1, 1)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=10)

    ops = [
        _make_operation(
            created_at=base_ts,
            status=OperationStatus.COMPLETED,
            client_id="c1",
            merchant_id="m1",
            product_type=ProductType.AI95,
            amount=1_000,
            quantity=Decimal("1.500"),
        ),
        _make_operation(
            created_at=base_ts + timedelta(minutes=15),
            status=OperationStatus.COMPLETED,
            client_id="c2",
            merchant_id="m1",
            product_type=ProductType.AI92,
            amount=500,
            quantity=None,
        ),
    ]

    session.add_all(ops)
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    summaries = session.query(BillingSummary).order_by(BillingSummary.client_id).all()

    assert len(summaries) == 2

    first = summaries[0]
    assert first.client_id == "c1"
    assert first.total_amount == 1_000
    assert first.total_quantity == Decimal("1.500")
    assert first.operations_count == 1
    assert first.commission_amount == 10

    second = summaries[1]
    assert second.client_id == "c2"
    assert second.total_amount == 500
    assert second.total_quantity is None
    assert second.operations_count == 1
    assert second.commission_amount == 5


def test_build_billing_summary_for_date_upserts(session):
    billing_date = date(2024, 2, 1)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=9)

    op1 = _make_operation(
        created_at=base_ts,
        status=OperationStatus.COMPLETED,
        client_id="c1",
        merchant_id="m1",
        product_type=ProductType.AI95,
        amount=1_000,
        quantity=Decimal("1.000"),
    )
    session.add(op1)
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    initial = session.query(BillingSummary).first()
    assert initial.total_amount == 1_000
    assert initial.operations_count == 1

    asyncio.run(build_billing_summary_for_date(billing_date))

    session.expire_all()
    updated = session.query(BillingSummary).first()
    assert updated.total_amount == 1_000
    assert updated.total_quantity == Decimal("1.000")
    assert updated.operations_count == 1
    assert updated.commission_amount == 10

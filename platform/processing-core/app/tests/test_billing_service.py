import asyncio
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.billing_period import BillingPeriod
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services import billing_service
from app.services.billing_service import build_billing_summary_for_date


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    support_metadata = MetaData()
    Table("fuel_stations", support_metadata, Column("id", String(36), primary_key=True))
    support_metadata.create_all(bind=engine)
    for table in (
        BillingPeriod.__table__,
        BillingSummary.__table__,
        Operation.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(billing_service, "SessionLocal", factory)

    try:
        yield factory
    finally:
        for table in reversed(
            (
                BillingSummary.__table__,
                BillingPeriod.__table__,
                Operation.__table__,
            )
        ):
            table.drop(bind=engine, checkfirst=True)
        support_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture()
def session(session_factory):
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _make_capture(
    *,
    created_at: datetime,
    merchant_id: str,
    client_id: str,
    amount: int,
    product_type: ProductType = ProductType.AI95,
) -> Operation:
    return Operation(
        ext_operation_id=f"capture-{merchant_id}-{client_id}-{created_at.timestamp()}",
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.COMPLETED,
        created_at=created_at,
        updated_at=created_at,
        merchant_id=merchant_id,
        terminal_id="terminal-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=product_type,
        amount=amount,
        currency="RUB",
        quantity=None,
        unit_price=None,
        captured_amount=amount,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_build_billing_summary_for_date_creates_merchant_level_summaries(session):
    billing_date = date(2024, 1, 1)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=10)

    session.add_all(
        [
            _make_capture(
                created_at=base_ts,
                merchant_id="m1",
                client_id="c1",
                amount=1_000,
            ),
            _make_capture(
                created_at=base_ts + timedelta(minutes=15),
                merchant_id="m1",
                client_id="c2",
                amount=500,
                product_type=ProductType.AI92,
            ),
            _make_capture(
                created_at=base_ts + timedelta(minutes=30),
                merchant_id="m2",
                client_id="c3",
                amount=700,
            ),
        ]
    )
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    summaries = session.query(BillingSummary).order_by(BillingSummary.merchant_id).all()

    assert len(summaries) == 2

    first = summaries[0]
    assert first.merchant_id == "m1"
    assert first.billing_date == billing_date
    assert first.total_amount == 1_500
    assert first.operations_count == 2
    assert first.status == BillingSummaryStatus.PENDING
    assert first.hash

    second = summaries[1]
    assert second.merchant_id == "m2"
    assert second.billing_date == billing_date
    assert second.total_amount == 700
    assert second.operations_count == 1
    assert second.status == BillingSummaryStatus.PENDING
    assert second.hash


def test_build_billing_summary_for_date_updates_existing_summary(session):
    billing_date = date(2024, 2, 1)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=9)

    session.add(
        _make_capture(
            created_at=base_ts,
            merchant_id="m1",
            client_id="c1",
            amount=1_000,
        )
    )
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    initial = session.query(BillingSummary).one()
    initial_id = initial.id
    assert initial.total_amount == 1_000
    assert initial.operations_count == 1

    session.add(
        _make_capture(
            created_at=base_ts + timedelta(minutes=10),
            merchant_id="m1",
            client_id="c2",
            amount=250,
        )
    )
    session.commit()

    asyncio.run(build_billing_summary_for_date(billing_date))

    session.expire_all()
    updated = session.query(BillingSummary).one()
    assert updated.id == initial_id
    assert updated.billing_date == billing_date
    assert updated.total_amount == 1_250
    assert updated.operations_count == 2
    assert updated.status == BillingSummaryStatus.PENDING
    assert updated.hash

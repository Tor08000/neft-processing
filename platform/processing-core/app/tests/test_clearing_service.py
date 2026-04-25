import asyncio
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing
from app.models.operation import ProductType
from app.services.clearing_service import generate_clearing_batches_for_date
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    tables = (
        BillingPeriod.__table__,
        BillingSummary.__table__,
        Clearing.__table__,
    )
    with scoped_session_context(tables=tables) as session:
        yield session


def _create_summary(session: Session, **kwargs) -> BillingSummary:
    billing_date = kwargs.get("billing_date")
    period_id = kwargs.get("billing_period_id")
    if billing_date and not period_id:
        start_at = datetime.combine(billing_date, datetime.min.time(), tzinfo=timezone.utc)
        end_at = datetime.combine(billing_date, datetime.max.time(), tzinfo=timezone.utc)
        period = (
            session.query(BillingPeriod)
            .filter(
                BillingPeriod.period_type == BillingPeriodType.DAILY,
                BillingPeriod.start_at == start_at,
                BillingPeriod.end_at == end_at,
            )
            .one_or_none()
        )
        if period is None:
            period = BillingPeriod(
                period_type=BillingPeriodType.DAILY,
                start_at=start_at,
                end_at=end_at,
                tz="UTC",
                status=BillingPeriodStatus.OPEN,
            )
            session.add(period)
            session.flush()
        kwargs["billing_period_id"] = period.id

    summary = BillingSummary(**kwargs)
    session.add(summary)
    session.commit()
    session.refresh(summary)
    return summary


def test_generate_creates_clearing_batches(db_session: Session):
    clearing_date = date(2024, 1, 10)
    _create_summary(
        db_session,
        billing_date=clearing_date,
        client_id="c1",
        merchant_id="m1",
        product_type=ProductType.DIESEL,
        currency="RUB",
        total_amount=1500,
        total_captured_amount=1500,
        operations_count=2,
        commission_amount=15,
    )

    asyncio.run(generate_clearing_batches_for_date(clearing_date, session=db_session))

    batches = db_session.query(Clearing).all()
    assert len(batches) == 1
    batch = batches[0]
    assert batch.total_amount == 1500
    assert batch.status == "PENDING"
    assert batch.details[0]["total_amount"] == 1500


def test_grouping_by_merchant_and_currency(db_session: Session):
    clearing_date = date(2024, 1, 11)
    _create_summary(
        db_session,
        billing_date=clearing_date,
        client_id="c1",
        merchant_id="m1",
        product_type=ProductType.AI92,
        currency="RUB",
        total_amount=1000,
        total_captured_amount=1000,
        operations_count=1,
        commission_amount=10,
    )
    _create_summary(
        db_session,
        billing_date=clearing_date,
        client_id="c2",
        merchant_id="m1",
        product_type=ProductType.AI95,
        currency="RUB",
        total_amount=500,
        total_captured_amount=500,
        operations_count=1,
        commission_amount=5,
    )
    _create_summary(
        db_session,
        billing_date=clearing_date,
        client_id="c3",
        merchant_id="m2",
        product_type=ProductType.AI95,
        currency="USD",
        total_amount=700,
        total_captured_amount=700,
        operations_count=1,
        commission_amount=7,
    )

    asyncio.run(generate_clearing_batches_for_date(clearing_date, session=db_session))

    batches = db_session.query(Clearing).order_by(Clearing.merchant_id, Clearing.currency).all()
    assert len(batches) == 2
    assert batches[0].merchant_id == "m1"
    assert batches[0].currency == "RUB"
    assert batches[0].total_amount == 1500
    assert len(batches[0].details) == 2

    assert batches[1].merchant_id == "m2"
    assert batches[1].currency == "USD"
    assert batches[1].total_amount == 700
    assert len(batches[1].details) == 1


def test_generate_is_idempotent(db_session: Session):
    clearing_date = date(2024, 1, 12)
    _create_summary(
        db_session,
        billing_date=clearing_date,
        client_id="c1",
        merchant_id="m1",
        product_type=ProductType.DIESEL,
        currency="RUB",
        total_amount=2000,
        total_captured_amount=2000,
        operations_count=2,
        commission_amount=20,
    )

    asyncio.run(generate_clearing_batches_for_date(clearing_date, session=db_session))
    asyncio.run(generate_clearing_batches_for_date(clearing_date, session=db_session))

    batches = db_session.query(Clearing).filter(Clearing.batch_date == clearing_date).all()
    assert len(batches) == 1
    assert batches[0].total_amount == 2000

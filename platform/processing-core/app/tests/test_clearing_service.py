import asyncio
from datetime import date

import pytest

from app.db import Base, SessionLocal, engine
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing
from app.models.operation import ProductType
from app.services.clearing_service import generate_clearing_batches_for_date


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _create_summary(**kwargs):
    session = SessionLocal()
    try:
        with session.begin():
            summary = BillingSummary(**kwargs)
            session.add(summary)
        return summary
    finally:
        session.close()


def test_generate_creates_clearing_batches():
    clearing_date = date(2024, 1, 10)
    _create_summary(
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

    asyncio.run(generate_clearing_batches_for_date(clearing_date))

    session = SessionLocal()
    try:
        batches = session.query(Clearing).all()
        assert len(batches) == 1
        batch = batches[0]
        assert batch.total_amount == 1500
        assert batch.status == "PENDING"
        assert batch.details[0]["total_amount"] == 1500
    finally:
        session.close()


def test_grouping_by_merchant_and_currency():
    clearing_date = date(2024, 1, 11)
    _create_summary(
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

    asyncio.run(generate_clearing_batches_for_date(clearing_date))

    session = SessionLocal()
    try:
        batches = session.query(Clearing).order_by(Clearing.merchant_id, Clearing.currency).all()
        assert len(batches) == 2
        assert batches[0].merchant_id == "m1"
        assert batches[0].currency == "RUB"
        assert batches[0].total_amount == 1500
        assert len(batches[0].details) == 2

        assert batches[1].merchant_id == "m2"
        assert batches[1].currency == "USD"
        assert batches[1].total_amount == 700
        assert len(batches[1].details) == 1
    finally:
        session.close()


def test_generate_is_idempotent():
    clearing_date = date(2024, 1, 12)
    _create_summary(
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

    asyncio.run(generate_clearing_batches_for_date(clearing_date))
    asyncio.run(generate_clearing_batches_for_date(clearing_date))

    session = SessionLocal()
    try:
        batches = session.query(Clearing).filter(Clearing.batch_date == clearing_date).all()
        assert len(batches) == 1
        assert batches[0].total_amount == 2000
    finally:
        session.close()


def test_generate_returns_empty_list_for_missing_summaries():
    clearing_date = date(2024, 1, 13)

    result = asyncio.run(generate_clearing_batches_for_date(clearing_date))
    assert result == []

    session = SessionLocal()
    try:
        batches = session.query(Clearing).filter(Clearing.batch_date == clearing_date).all()
        assert batches == []
    finally:
        session.close()

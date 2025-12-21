from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine, reset_engine
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing.daily import finalize_billing_day, run_billing_daily


@pytest.fixture(autouse=True)
def _use_sqlite(monkeypatch: pytest.MonkeyPatch):
    import app.db as db

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite:///:memory:", raising=False)
    monkeypatch.setattr(db, "raw_db_url", "sqlite:///:memory:", raising=False)
    reset_engine()


@pytest.fixture(autouse=True)
def _setup_db(_use_sqlite):
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
    client_id: str = "c1",
    merchant_id: str = "m1",
    product_type: ProductType | None = ProductType.AI92,
    amount: int = 1_000,
    quantity: Decimal | None = None,
):
    op_type = OperationType.COMMIT if status == OperationStatus.COMPLETED else OperationType.REFUND
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
        currency="RUB",
        quantity=quantity,
        unit_price=None,
        captured_amount=amount if status == OperationStatus.COMPLETED else 0,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_billing_summary_upsert_idempotent(session):
    billing_date = date(2024, 3, 10)
    base_ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=8)

    session.add_all(
        [
            _make_operation(
                created_at=base_ts,
                status=OperationStatus.COMPLETED,
                amount=1_000,
                quantity=Decimal("1.0"),
            ),
        ]
    )
    session.commit()

    summaries_first = run_billing_daily(billing_date, session=session)
    summaries_second = run_billing_daily(billing_date, session=session)

    summary = session.query(BillingSummary).first()
    assert summary.total_amount == 1_000
    assert summary.operations_count == 1
    assert summary.status == BillingSummaryStatus.PENDING
    assert len(summaries_first) == len(summaries_second) == 1


def test_billing_finalize_blocks_updates(session):
    billing_date = date(2024, 4, 5)
    ts = datetime.combine(billing_date, datetime.min.time()) + timedelta(hours=9)

    first_op = _make_operation(
        created_at=ts,
        status=OperationStatus.COMPLETED,
        amount=500,
        quantity=Decimal("0.5"),
    )
    session.add(first_op)
    session.commit()

    run_billing_daily(billing_date, session=session)
    finalize_billing_day(
        billing_date,
        session=session,
        now=datetime.combine(billing_date, datetime.max.time()) + timedelta(hours=13),
    )

    second_op = _make_operation(
        created_at=ts + timedelta(hours=1),
        status=OperationStatus.COMPLETED,
        amount=1_000,
        quantity=Decimal("1.0"),
    )
    session.add(second_op)
    session.commit()

    run_billing_daily(billing_date, session=session)

    finalized_summary = session.query(BillingSummary).filter_by(billing_date=billing_date).first()

    assert finalized_summary.total_amount == 500
    assert finalized_summary.operations_count == 1
    assert finalized_summary.status == BillingSummaryStatus.FINALIZED

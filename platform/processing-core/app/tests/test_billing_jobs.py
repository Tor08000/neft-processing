from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.billing_job_run import BillingJobRun
from app.models.billing_period import BillingPeriod
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing import daily as billing_daily
from app.services.billing.daily import finalize_billing_day, run_billing_daily


TEST_TABLES = (
    BillingPeriod.__table__,
    BillingSummary.__table__,
    BillingJobRun.__table__,
    Operation.__table__,
)


@pytest.fixture
def _session_factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    stub_metadata = MetaData()
    Table("fuel_stations", stub_metadata, Column("id", String(36), primary_key=True))
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    monkeypatch.setattr(billing_daily, "_aggregate_fuel_transactions", lambda _session, _billing_date: [])

    session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    try:
        yield session_local
    finally:
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture
def session(_session_factory):
    db = _session_factory()
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
    assert summary.hash
    assert len(summaries_first) == len(summaries_second) == 1
    assert summaries_first[0].hash == summaries_second[0].hash == summary.hash


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

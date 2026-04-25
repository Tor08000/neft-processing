from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.contract_limits import TariffPlan, TariffPrice
from app.models.fuel import FuelNetwork, FuelStation, FuelStationNetwork
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.billing_service import BillingCalculationResult, calculate_client_charges


TEST_TABLES = (
    TariffPlan.__table__,
    TariffPrice.__table__,
    FuelNetwork.__table__,
    FuelStationNetwork.__table__,
    FuelStation.__table__,
    Operation.__table__,
)


@pytest.fixture(autouse=True)
def _prepare_db():
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

    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

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
        engine.dispose()


@pytest.fixture
def session(_prepare_db):
    db = _prepare_db()
    try:
        yield db
    finally:
        db.close()


def _make_operation(
    *,
    created_at: datetime,
    status: OperationStatus,
    client_id: str,
    tariff_id: str,
    product_id: str,
    merchant_id: str,
    terminal_id: str,
    quantity: Decimal,
    amount: int = 1_000,
    currency: str = "RUB",
    operation_type: OperationType = OperationType.COMMIT,
) -> Operation:
    return Operation(
        ext_operation_id=f"op-{created_at.timestamp()}-{tariff_id}-{product_id}-{status.value}",
        operation_type=operation_type,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        client_id=client_id,
        card_id="card-1",
        tariff_id=tariff_id,
        product_id=product_id,
        product_type=ProductType[product_id] if product_id in ProductType.__members__ else None,
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


def _add_price(
    db,
    *,
    tariff_id: str,
    product_id: str,
    price: str,
    cost_price: str,
    partner_id: str | None = None,
    priority: int = 100,
):
    price_obj = TariffPrice(
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        price_per_liter=Decimal(price),
        cost_price_per_liter=Decimal(cost_price),
        currency="RUB",
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        priority=priority,
    )
    db.add(price_obj)
    db.commit()
    db.refresh(price_obj)
    return price_obj


def test_calculates_totals_for_multiple_operations(session):
    now = datetime.now(timezone.utc)
    session.add(TariffPlan(id="tariff-main", name="Main"))
    session.commit()
    _add_price(session, tariff_id="tariff-main", product_id="AI95", price="50", cost_price="40")

    ops = [
        _make_operation(
            created_at=now - timedelta(minutes=10),
            status=OperationStatus.POSTED,
            client_id="client-1",
            tariff_id="tariff-main",
            product_id="AI95",
            merchant_id="partner-1",
            terminal_id="azs-1",
            quantity=Decimal("10"),
            amount=1_000,
        ),
        _make_operation(
            created_at=now - timedelta(minutes=5),
            status=OperationStatus.COMPLETED,
            client_id="client-1",
            tariff_id="tariff-main",
            product_id="AI95",
            merchant_id="partner-1",
            terminal_id="azs-1",
            quantity=Decimal("5"),
            amount=500,
        ),
    ]
    session.add_all(ops)
    session.commit()

    result: BillingCalculationResult = calculate_client_charges(
        session,
        client_id="client-1",
        date_from=now - timedelta(hours=1),
        date_to=now + timedelta(minutes=1),
    )

    totals = result.totals_by_currency["RUB"]
    assert totals.charge_amount == Decimal("750")
    assert totals.cost_amount == Decimal("600")
    assert totals.margin_amount == Decimal("150")
    assert len(result.items) == 2


def test_partner_prices_and_refunds_affect_totals(session):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            TariffPlan(id="t1", name="Standard"),
            TariffPlan(id="t2", name="Premium"),
        ]
    )
    session.commit()

    _add_price(session, tariff_id="t1", product_id="DIESEL", price="50", cost_price="40")
    _add_price(
        session,
        tariff_id="t2",
        product_id="DIESEL",
        price="70",
        cost_price="55",
        partner_id="partner-2",
        priority=10,
    )

    ops = [
        _make_operation(
            created_at=now - timedelta(minutes=30),
            status=OperationStatus.POSTED,
            client_id="client-2",
            tariff_id="t1",
            product_id="DIESEL",
            merchant_id="partner-1",
            terminal_id="azs-1",
            quantity=Decimal("4"),
            amount=400,
        ),
        _make_operation(
            created_at=now - timedelta(minutes=20),
            status=OperationStatus.POSTED,
            client_id="client-2",
            tariff_id="t2",
            product_id="DIESEL",
            merchant_id="partner-2",
            terminal_id="azs-2",
            quantity=Decimal("3"),
            amount=300,
        ),
        _make_operation(
            created_at=now - timedelta(minutes=10),
            status=OperationStatus.REFUNDED,
            client_id="client-2",
            tariff_id="t1",
            product_id="DIESEL",
            merchant_id="partner-1",
            terminal_id="azs-1",
            quantity=Decimal("2"),
            amount=200,
            operation_type=OperationType.REFUND,
        ),
    ]

    session.add_all(ops)
    session.commit()

    result = calculate_client_charges(
        session,
        client_id="client-2",
        date_from=now - timedelta(hours=1),
        date_to=now + timedelta(minutes=1),
    )

    totals = result.totals_by_currency["RUB"]
    assert totals.charge_amount == Decimal("310")
    assert totals.cost_amount == Decimal("245")
    assert totals.margin_amount == Decimal("65")
    assert len(result.items) == 3

    refund_line = next(item for item in result.items if item.charge_amount < 0)
    assert refund_line.charge_amount < 0
    assert refund_line.quantity < 0

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.account import Account, AccountBalance
from app.models.clearing import Clearing
from app.models.ledger_entry import LedgerEntry
from app.models.payout_event import PayoutEvent
from app.models.payout_order import PayoutOrder, PayoutOrderStatus
from app.models.settlement import Settlement
from app.services.settlements import (
    approve_settlement,
    confirm_payout,
    generate_settlements_for_date,
    partner_balances,
    send_payout,
    SettlementError,
)


_SETTLEMENTS_TEST_METADATA = MetaData()

CARDS_REFLECTED = Table(
    "cards",
    _SETTLEMENTS_TEST_METADATA,
    Column("id", String(64), primary_key=True),
)

OPERATIONS_REFLECTED = Table(
    "operations",
    _SETTLEMENTS_TEST_METADATA,
    Column("id", String(36), primary_key=True),
)

SETTLEMENTS_TEST_TABLES = (
    CARDS_REFLECTED,
    OPERATIONS_REFLECTED,
    Clearing.__table__,
    Settlement.__table__,
    PayoutOrder.__table__,
    PayoutEvent.__table__,
    Account.__table__,
    AccountBalance.__table__,
    LedgerEntry.__table__,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    for table in SETTLEMENTS_TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(SETTLEMENTS_TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


def _seed_clearing(
    db: Session,
    *,
    merchant_id: str = "11111111-1111-1111-1111-111111111111",
    currency: str = "RUB",
    total_amount: int = 1000,
):
    clearing = Clearing(
        batch_date=date(2025, 12, 1),
        merchant_id=merchant_id,
        currency=currency,
        total_amount=total_amount,
        status="PENDING",
    )
    db.add(clearing)
    db.commit()
    db.refresh(clearing)
    return clearing


def test_generate_creates_settlement(db: Session):
    _seed_clearing(db)
    settlements = generate_settlements_for_date(db, target_date=date(2025, 12, 1))
    assert len(settlements) == 1
    settlement = settlements[0]
    assert settlement.status == "DRAFT"
    assert settlement.total_amount == 1000


def test_approve_and_send_flow_creates_payout_and_ledger(db: Session):
    _seed_clearing(db)
    settlement = generate_settlements_for_date(db, target_date=date(2025, 12, 1))[0]
    approved = approve_settlement(db, settlement.id)
    assert approved.status == "APPROVED"
    payout = approved.payout_order
    assert payout is not None
    sent = send_payout(db, payout.id)
    assert sent.status == "SENT"
    assert sent.settlement.status == "SENT"

    confirmed = confirm_payout(db, payout.id)
    assert confirmed.status == "CONFIRMED"
    assert confirmed.settlement.status == "CONFIRMED"

    balances = partner_balances(db, partner_id=settlement.partner_id)
    assert any(item.balance == Decimal("1000") for item in balances)


def test_invalid_send_raises_error(db: Session):
    _seed_clearing(db)
    settlement = generate_settlements_for_date(db, target_date=date(2025, 12, 1))[0]
    payout = approve_settlement(db, settlement.id).payout_order
    payout.status = PayoutOrderStatus.CONFIRMED
    db.commit()
    with pytest.raises(SettlementError):
        send_payout(db, payout.id)

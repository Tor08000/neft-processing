from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.clearing import Clearing
from app.models.payout_order import PayoutOrderStatus
from app.services.settlements import (
    approve_settlement,
    confirm_payout,
    generate_settlements_for_date,
    partner_balances,
    send_payout,
    SettlementError,
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
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_clearing(db: Session, *, merchant_id: str = "m-1", currency: str = "RUB", total_amount: int = 1000):
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

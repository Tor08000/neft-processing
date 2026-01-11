from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.marketplace_commissions import (
    MarketplaceCommissionRule,
    MarketplaceCommissionScope,
    MarketplaceCommissionStatus,
    MarketplaceCommissionType,
)
from app.models.marketplace_orders import MarketplaceOrder
from app.services.marketplace_commission_service import MarketplaceCommissionService


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    MarketplaceCommissionRule.__table__.create(bind=engine)
    MarketplaceOrder.__table__.create(bind=engine)
    return SessionLocal()


def test_commission_percent_with_min_max() -> None:
    db = _session()
    try:
        rule = MarketplaceCommissionRule(
            id=str(uuid4()),
            scope=MarketplaceCommissionScope.MARKETPLACE.value,
            commission_type=MarketplaceCommissionType.PERCENT.value,
            rate=Decimal("0.1"),
            min_commission=Decimal("50"),
            max_commission=Decimal("80"),
            status=MarketplaceCommissionStatus.ACTIVE.value,
        )
        db.add(rule)
        order = MarketplaceOrder(
            id=str(uuid4()),
            client_id=str(uuid4()),
            partner_id=str(uuid4()),
            product_id=str(uuid4()),
            quantity=Decimal("1"),
            price_snapshot={"subtotal": "1000"},
            status="CREATED",
        )
        db.add(order)
        db.commit()

        snapshot = MarketplaceCommissionService(db).calculate_snapshot(
            order=order,
            product_category=None,
            subtotal=Decimal("1000"),
        )
        assert snapshot.amount == Decimal("80")
    finally:
        db.close()


def test_commission_fixed_amount() -> None:
    db = _session()
    try:
        rule = MarketplaceCommissionRule(
            id=str(uuid4()),
            scope=MarketplaceCommissionScope.MARKETPLACE.value,
            commission_type=MarketplaceCommissionType.FIXED.value,
            amount=Decimal("25"),
            status=MarketplaceCommissionStatus.ACTIVE.value,
        )
        db.add(rule)
        order = MarketplaceOrder(
            id=str(uuid4()),
            client_id=str(uuid4()),
            partner_id=str(uuid4()),
            product_id=str(uuid4()),
            quantity=Decimal("1"),
            price_snapshot={"subtotal": "100"},
            status="CREATED",
        )
        db.add(order)
        db.commit()

        snapshot = MarketplaceCommissionService(db).calculate_snapshot(
            order=order,
            product_category=None,
            subtotal=Decimal("100"),
        )
        assert snapshot.amount == Decimal("25")
    finally:
        db.close()


def test_commission_tiered_rate() -> None:
    db = _session()
    try:
        rule = MarketplaceCommissionRule(
            id=str(uuid4()),
            scope=MarketplaceCommissionScope.MARKETPLACE.value,
            commission_type=MarketplaceCommissionType.TIERED.value,
            tiers=[
                {"from": "0", "to": "100", "rate": "0.05"},
                {"from": "100", "to": None, "rate": "0.1"},
            ],
            status=MarketplaceCommissionStatus.ACTIVE.value,
        )
        db.add(rule)
        order = MarketplaceOrder(
            id=str(uuid4()),
            client_id=str(uuid4()),
            partner_id=str(uuid4()),
            product_id=str(uuid4()),
            quantity=Decimal("1"),
            price_snapshot={"subtotal": "200"},
            status="CREATED",
        )
        db.add(order)
        db.commit()

        snapshot = MarketplaceCommissionService(db).calculate_snapshot(
            order=order,
            product_category=None,
            subtotal=Decimal("200"),
        )
        assert snapshot.amount == Decimal("20")
    finally:
        db.close()

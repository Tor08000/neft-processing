from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.marketplace_catalog import MarketplacePriceModel, MarketplaceProduct, MarketplaceProductStatus, MarketplaceProductType
from app.models.marketplace_promotions import (
    MarketplaceCoupon,
    MarketplaceCouponBatch,
    MarketplaceCouponBatchType,
    MarketplaceCouponStatus,
    MarketplacePromotion,
    MarketplacePromotionStatus,
    MarketplacePromotionType,
    MarketplacePromotionApplication,
)
from app.services.marketplace_pricing_service import MarketplacePricingService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        MarketplaceProduct.__table__,
        MarketplacePromotion.__table__,
        MarketplaceCouponBatch.__table__,
        MarketplaceCoupon.__table__,
        MarketplacePromotionApplication.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(tables):
            table.drop(bind=engine)
        engine.dispose()


def _create_product(db, partner_id: str, price: int = 1000) -> MarketplaceProduct:
    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=partner_id,
        type=MarketplaceProductType.PRODUCT,
        title="Oil",
        description="Engine oil",
        category="OILS",
        price_model=MarketplacePriceModel.FIXED,
        price_config={"amount": price, "currency": "RUB"},
        status=MarketplaceProductStatus.PUBLISHED,
    )
    db.add(product)
    db.commit()
    return product


def _create_promotion(db, partner_id: str, *, rules: dict, scope: dict | None = None) -> MarketplacePromotion:
    promo = MarketplacePromotion(
        id=str(uuid4()),
        partner_id=partner_id,
        promo_type=MarketplacePromotionType.PARTNER_STORE_DISCOUNT,
        status=MarketplacePromotionStatus.ACTIVE,
        title="Promo",
        description="",
        scope_json=scope or {"type": "PARTNER", "partner_id": partner_id},
        rules_json=rules,
    )
    db.add(promo)
    db.commit()
    return promo


def test_percent_discount(db_session) -> None:
    partner_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "PERCENT", "discount_value": 10, "stacking": "BEST_ONLY"},
    )
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=str(uuid4()),
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
    )
    assert pricing.price_snapshot["final"]["items_total"] == 900.0


def test_fixed_discount_with_floor(db_session) -> None:
    partner_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "FIXED", "discount_value": 200, "price_floor": 950, "stacking": "BEST_ONLY"},
    )
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=str(uuid4()),
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
    )
    assert pricing.price_snapshot["final"]["items_total"] == 950.0
    assert pricing.price_snapshot["rules"]["price_floor_hit"] is True


def test_best_only_selection(db_session) -> None:
    partner_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "PERCENT", "discount_value": 10, "stacking": "BEST_ONLY"},
    )
    best = _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "FIXED", "discount_value": 300, "stacking": "BEST_ONLY"},
    )
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=str(uuid4()),
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
    )
    assert pricing.applied_promotion_id == str(best.id)
    assert pricing.price_snapshot["final"]["items_total"] == 700.0


def test_coupon_override(db_session) -> None:
    partner_id = str(uuid4())
    client_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "PERCENT", "discount_value": 20, "stacking": "BEST_ONLY"},
    )
    coupon_promo = _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "PERCENT", "discount_value": 5, "stacking": "BEST_ONLY"},
    )
    batch = MarketplaceCouponBatch(
        id=str(uuid4()),
        partner_id=partner_id,
        promotion_id=str(coupon_promo.id),
        batch_type=MarketplaceCouponBatchType.PUBLIC,
        total_count=1,
    )
    coupon = MarketplaceCoupon(
        id=str(uuid4()),
        batch_id=batch.id,
        promotion_id=str(coupon_promo.id),
        code="TESTCODE",
        status=MarketplaceCouponStatus.NEW,
    )
    db_session.add(batch)
    db_session.add(coupon)
    db_session.commit()
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=client_id,
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
        coupon_code="TESTCODE",
    )
    assert pricing.applied_promotion_id == str(coupon_promo.id)
    assert pricing.price_snapshot["final"]["items_total"] == 950.0


def test_schedule_window(db_session) -> None:
    partner_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    promo = _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "PERCENT", "discount_value": 10, "stacking": "BEST_ONLY"},
    )
    promo.schedule_json = {"valid_from": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    db_session.commit()
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=str(uuid4()),
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
    )
    assert pricing.price_snapshot["final"]["items_total"] == 1000.0


def test_limits_block_promotion(db_session) -> None:
    partner_id = str(uuid4())
    client_id = str(uuid4())
    product = _create_product(db_session, partner_id, price=1000)
    promo = _create_promotion(
        db_session,
        partner_id,
        rules={"discount_type": "FIXED", "discount_value": 100, "stacking": "BEST_ONLY"},
    )
    promo.limits_json = {"total_redemptions": 1}
    application = MarketplacePromotionApplication(
        id=str(uuid4()),
        order_id=str(uuid4()),
        partner_id=partner_id,
        client_id=client_id,
        promotion_id=str(promo.id),
        coupon_id=None,
        applied_discount=Decimal("100"),
        currency="RUB",
        price_snapshot_json={},
        decision_json={},
    )
    db_session.add(application)
    db_session.commit()
    service = MarketplacePricingService(db_session)
    pricing = service.quote(
        partner_id=partner_id,
        client_id=client_id,
        items=[{"product_id": product.id, "quantity": Decimal("1")}],
    )
    assert pricing.price_snapshot["final"]["items_total"] == 1000.0

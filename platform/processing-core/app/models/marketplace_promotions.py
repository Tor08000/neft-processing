from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class MarketplacePromotionType(str, Enum):
    PRODUCT_DISCOUNT = "PRODUCT_DISCOUNT"
    CATEGORY_DISCOUNT = "CATEGORY_DISCOUNT"
    PARTNER_STORE_DISCOUNT = "PARTNER_STORE_DISCOUNT"
    COUPON_PROMO = "COUPON_PROMO"


class MarketplacePromotionStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ENDED = "ENDED"
    ARCHIVED = "ARCHIVED"


class MarketplaceCouponBatchType(str, Enum):
    PUBLIC = "PUBLIC"
    TARGETED = "TARGETED"


class MarketplaceCouponStatus(str, Enum):
    NEW = "NEW"
    ISSUED = "ISSUED"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


class MarketplacePromotion(Base):
    __tablename__ = "marketplace_promotions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    promo_type = Column(
        ExistingEnum(MarketplacePromotionType, name="marketplace_promotion_type"),
        nullable=False,
    )
    status = Column(
        ExistingEnum(MarketplacePromotionStatus, name="marketplace_promotion_status"),
        nullable=False,
        default=MarketplacePromotionStatus.DRAFT.value,
    )
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope_json = Column(JSON_TYPE, nullable=False)
    eligibility_json = Column(JSON_TYPE, nullable=True)
    rules_json = Column(JSON_TYPE, nullable=False)
    schedule_json = Column(JSON_TYPE, nullable=True)
    limits_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    created_by = Column(GUID(), nullable=True)
    updated_by = Column(GUID(), nullable=True)


class MarketplaceCouponBatch(Base):
    __tablename__ = "marketplace_coupon_batches"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    promotion_id = Column(GUID(), ForeignKey("marketplace_promotions.id", ondelete="RESTRICT"), nullable=False)
    batch_type = Column(
        ExistingEnum(MarketplaceCouponBatchType, name="marketplace_coupon_batch_type"),
        nullable=False,
    )
    code_prefix = Column(Text, nullable=True)
    total_count = Column(Integer, nullable=False)
    issued_count = Column(Integer, nullable=False, server_default="0")
    redeemed_count = Column(Integer, nullable=False, server_default="0")
    meta_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class MarketplaceCoupon(Base):
    __tablename__ = "marketplace_coupons"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    batch_id = Column(GUID(), ForeignKey("marketplace_coupon_batches.id", ondelete="RESTRICT"), nullable=False)
    promotion_id = Column(GUID(), ForeignKey("marketplace_promotions.id", ondelete="RESTRICT"), nullable=False)
    code = Column(Text, nullable=False, unique=True, index=True)
    status = Column(
        ExistingEnum(MarketplaceCouponStatus, name="marketplace_coupon_status"),
        nullable=False,
        default=MarketplaceCouponStatus.NEW.value,
    )
    client_id = Column(GUID(), nullable=True, index=True)
    redeemed_order_id = Column(GUID(), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplacePromotionApplication(Base):
    __tablename__ = "marketplace_promotion_applications"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    order_id = Column(GUID(), ForeignKey("marketplace_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    client_id = Column(GUID(), nullable=False, index=True)
    promotion_id = Column(GUID(), ForeignKey("marketplace_promotions.id", ondelete="RESTRICT"), nullable=False)
    coupon_id = Column(GUID(), ForeignKey("marketplace_coupons.id", ondelete="RESTRICT"), nullable=True)
    applied_discount = Column(Numeric(18, 4), nullable=False)
    currency = Column(Text, nullable=False)
    price_snapshot_json = Column(JSON_TYPE, nullable=False)
    decision_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


__all__ = [
    "MarketplaceCoupon",
    "MarketplaceCouponBatch",
    "MarketplaceCouponBatchType",
    "MarketplaceCouponStatus",
    "MarketplacePromotion",
    "MarketplacePromotionApplication",
    "MarketplacePromotionStatus",
    "MarketplacePromotionType",
]

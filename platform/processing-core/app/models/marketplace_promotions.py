from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class PromotionType(str, Enum):
    PRODUCT_DISCOUNT = "PRODUCT_DISCOUNT"
    CATEGORY_DISCOUNT = "CATEGORY_DISCOUNT"
    BUNDLE_DISCOUNT = "BUNDLE_DISCOUNT"
    TIER_DISCOUNT = "TIER_DISCOUNT"
    PUBLIC_COUPON = "PUBLIC_COUPON"
    TARGETED_COUPON = "TARGETED_COUPON"
    AUTO_COUPON = "AUTO_COUPON"
    FLASH_SALE = "FLASH_SALE"
    HAPPY_HOURS = "HAPPY_HOURS"
    SPONSORED_PLACEMENT = "SPONSORED_PLACEMENT"


class PromotionStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ENDED = "ENDED"
    ARCHIVED = "ARCHIVED"


class CouponStatus(str, Enum):
    NEW = "NEW"
    ISSUED = "ISSUED"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


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


class PromoBudgetModel(str, Enum):
    CPA = "CPA"
    CPC = "CPC"


class PromoBudgetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EXHAUSTED = "EXHAUSTED"


class MissionProgressStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CLAIMED = "CLAIMED"
    EXPIRED = "EXPIRED"


class PromotionApplicationImmutableError(ValueError):
    """Raised when WORM-protected promotion application records are mutated."""


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    partner_id = Column(GUID(), nullable=False, index=True)
    promo_type = Column(ExistingEnum(PromotionType, name="promotion_type"), nullable=False)
    status = Column(
        ExistingEnum(PromotionStatus, name="promotion_status"),
        nullable=False,
        default=PromotionStatus.DRAFT.value,
    )
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(JSON_TYPE, nullable=False)
    eligibility = Column(JSON_TYPE, nullable=False)
    rules = Column(JSON_TYPE, nullable=False)
    budget = Column(JSON_TYPE, nullable=True)
    limits = Column(JSON_TYPE, nullable=True)
    schedule = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    audit_event_id = Column(GUID(), nullable=True)


class CouponBatch(Base):
    __tablename__ = "coupon_batches"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    partner_id = Column(GUID(), nullable=False)
    promotion_id = Column(GUID(), ForeignKey("promotions.id", ondelete="RESTRICT"), nullable=False)
    code_prefix = Column(Text, nullable=True)
    total_count = Column(Numeric(18, 0), nullable=True)
    issued_count = Column(Numeric(18, 0), nullable=False, default=0)
    redeemed_count = Column(Numeric(18, 0), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    batch_id = Column(GUID(), ForeignKey("coupon_batches.id", ondelete="RESTRICT"), nullable=False)
    code = Column(Text, nullable=False, unique=True, index=True)
    status = Column(ExistingEnum(CouponStatus, name="coupon_status"), nullable=False)
    client_id = Column(GUID(), nullable=True)
    redeemed_order_id = Column(GUID(), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class PromoBudget(Base):
    __tablename__ = "promo_budgets"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    promotion_id = Column(GUID(), ForeignKey("promotions.id", ondelete="RESTRICT"), nullable=False)
    model = Column(ExistingEnum(PromoBudgetModel, name="promo_budget_model"), nullable=False)
    currency = Column(Text, nullable=False, default="RUB")
    total_budget = Column(Numeric(18, 2), nullable=False)
    spent_budget = Column(Numeric(18, 2), nullable=False, default=0)
    max_bid = Column(Numeric(18, 2), nullable=False)
    daily_cap = Column(Numeric(18, 2), nullable=True)
    status = Column(
        ExistingEnum(PromoBudgetStatus, name="promo_budget_status"),
        nullable=False,
        default=PromoBudgetStatus.ACTIVE.value,
    )
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PromotionApplication(Base):
    __tablename__ = "promotion_applications"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    promotion_id = Column(GUID(), ForeignKey("promotions.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(GUID(), ForeignKey("marketplace_orders.id", ondelete="RESTRICT"), nullable=False)
    partner_id = Column(GUID(), nullable=False)
    client_id = Column(GUID(), nullable=False)
    applied_discount = Column(Numeric(18, 2), nullable=False)
    applied_reason = Column(JSON_TYPE, nullable=False)
    final_price_snapshot = Column(JSON_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    audit_event_id = Column(GUID(), nullable=True)


class MarketplacePromotion(Base):
    __tablename__ = "marketplace_promotions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    partner_id = Column(GUID(), nullable=False)
    promo_type = Column(ExistingEnum(MarketplacePromotionType, name="marketplace_promotion_type"), nullable=False)
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
    partner_id = Column(GUID(), nullable=False)
    promotion_id = Column(GUID(), ForeignKey("marketplace_promotions.id", ondelete="RESTRICT"), nullable=False)
    batch_type = Column(ExistingEnum(MarketplaceCouponBatchType, name="marketplace_coupon_batch_type"), nullable=False)
    code_prefix = Column(Text, nullable=True)
    total_count = Column(Integer, nullable=False)
    issued_count = Column(Integer, nullable=False, default=0)
    redeemed_count = Column(Integer, nullable=False, default=0)
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
    status = Column(ExistingEnum(MarketplaceCouponStatus, name="marketplace_coupon_status"), nullable=False)
    client_id = Column(GUID(), nullable=True)
    redeemed_order_id = Column(GUID(), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplacePromotionApplication(Base):
    __tablename__ = "marketplace_promotion_applications"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(GUID(), nullable=True)
    order_id = Column(GUID(), ForeignKey("marketplace_orders.id", ondelete="RESTRICT"), nullable=False)
    partner_id = Column(GUID(), nullable=False)
    client_id = Column(GUID(), nullable=False)
    promotion_id = Column(GUID(), ForeignKey("marketplace_promotions.id", ondelete="RESTRICT"), nullable=False)
    coupon_id = Column(GUID(), ForeignKey("marketplace_coupons.id", ondelete="RESTRICT"), nullable=True)
    applied_discount = Column(Numeric(18, 4), nullable=False)
    currency = Column(Text, nullable=False)
    price_snapshot_json = Column(JSON_TYPE, nullable=False)
    decision_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PartnerTier(Base):
    __tablename__ = "partner_tiers"

    tier_code = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    benefits = Column(JSON_TYPE, nullable=False)
    thresholds = Column(JSON_TYPE, nullable=False)


class PartnerTierState(Base):
    __tablename__ = "partner_tier_state"

    partner_id = Column(GUID(), primary_key=True)
    tier_code = Column(Text, ForeignKey("partner_tiers.tier_code", ondelete="RESTRICT"), nullable=False)
    score = Column(Numeric(18, 2), nullable=False)
    metrics_snapshot = Column(JSON_TYPE, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=False)


class PartnerMission(Base):
    __tablename__ = "partner_missions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    rule = Column(JSON_TYPE, nullable=False)
    reward = Column(JSON_TYPE, nullable=False)
    active = Column(postgresql.BOOLEAN, nullable=False, default=True)


class PartnerMissionProgress(Base):
    __tablename__ = "partner_mission_progress"

    partner_id = Column(GUID(), primary_key=True)
    mission_id = Column(GUID(), ForeignKey("partner_missions.id", ondelete="RESTRICT"), primary_key=True)
    progress = Column(Numeric(18, 2), nullable=False)
    status = Column(ExistingEnum(MissionProgressStatus, name="partner_mission_status"), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class PartnerBadge(Base):
    __tablename__ = "partner_badges"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    code = Column(Text, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(Text, nullable=True)
    rule = Column(JSON_TYPE, nullable=False)


class PartnerBadgeAward(Base):
    __tablename__ = "partner_badge_awards"

    partner_id = Column(GUID(), primary_key=True)
    badge_id = Column(GUID(), ForeignKey("partner_badges.id", ondelete="RESTRICT"), primary_key=True)
    awarded_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)


@event.listens_for(PromotionApplication, "before_update")
@event.listens_for(PromotionApplication, "before_delete")
def _block_promotion_application_mutation(mapper, connection, target: PromotionApplication) -> None:
    raise PromotionApplicationImmutableError("promotion_application_immutable")


__all__ = [
    "Coupon",
    "CouponBatch",
    "CouponStatus",
    "MissionProgressStatus",
    "PartnerBadge",
    "PartnerBadgeAward",
    "PartnerMission",
    "PartnerMissionProgress",
    "PartnerTier",
    "PartnerTierState",
    "PromoBudget",
    "PromoBudgetModel",
    "PromoBudgetStatus",
    "Promotion",
    "PromotionApplication",
    "PromotionApplicationImmutableError",
    "PromotionStatus",
    "PromotionType",
]

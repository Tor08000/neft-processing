from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


PromotionType = Literal[
    "PRODUCT_DISCOUNT",
    "CATEGORY_DISCOUNT",
    "BUNDLE_DISCOUNT",
    "TIER_DISCOUNT",
    "PUBLIC_COUPON",
    "TARGETED_COUPON",
    "AUTO_COUPON",
    "FLASH_SALE",
    "HAPPY_HOURS",
    "SPONSORED_PLACEMENT",
]

PromotionStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"]


class PromotionCreate(BaseModel):
    promo_type: PromotionType
    title: str
    description: str | None = None
    scope: dict
    eligibility: dict = Field(default_factory=dict)
    rules: dict
    budget: dict | None = None
    limits: dict | None = None
    schedule: dict


class PromotionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    scope: dict | None = None
    eligibility: dict | None = None
    rules: dict | None = None
    budget: dict | None = None
    limits: dict | None = None
    schedule: dict | None = None


class PromotionOut(BaseModel):
    id: str
    tenant_id: int
    partner_id: str
    promo_type: PromotionType
    status: PromotionStatus
    title: str
    description: str | None = None
    scope: dict
    eligibility: dict
    rules: dict
    budget: dict | None = None
    limits: dict | None = None
    schedule: dict
    created_at: datetime
    updated_at: datetime | None = None
    audit_event_id: str | None = None


class PromotionListResponse(BaseModel):
    items: list[PromotionOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class PromotionStatsOut(BaseModel):
    promotion_id: str
    orders_count: int
    total_discount: Decimal
    last_applied_at: datetime | None = None


class CouponApplyRequest(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    coupon_code: str


class CouponApplyResponse(BaseModel):
    base_price: Decimal
    discount_total: Decimal
    final_price: Decimal
    applied_promotions: list[str] = Field(default_factory=list)
    price_snapshot: dict

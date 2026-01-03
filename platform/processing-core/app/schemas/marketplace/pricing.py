from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class QuoteItem(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)


class QuoteRequest(BaseModel):
    items: list[QuoteItem]
    coupon_code: str | None = None
    idempotency_key: str | None = None


class QuoteResponse(BaseModel):
    price_snapshot: dict
    applied_promotions: dict | None = None
    coupon_code: str | None = None


class DealPromotionOut(BaseModel):
    id: str
    partner_id: str
    promo_type: str
    title: str
    description: str | None = None
    scope_json: dict
    rules_json: dict
    schedule_json: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None


class DealListResponse(BaseModel):
    items: list[DealPromotionOut]
    total: int
    limit: int
    offset: int


StackingRule = Literal["BEST_ONLY"]

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.marketplace.catalog import ProductListOut


MarketplaceEventType = Literal["VIEW", "CLICK", "ADD_TO_CART", "PURCHASE", "REFUND"]


class MarketplaceEventCreate(BaseModel):
    event_type: MarketplaceEventType
    product_id: str | None = None
    partner_id: str | None = None
    context: dict | None = None
    meta: dict | None = None


class MarketplaceEventOut(BaseModel):
    id: str
    client_id: str
    user_id: str | None = None
    partner_id: str | None = None
    product_id: str | None = None
    event_type: MarketplaceEventType
    event_ts: datetime
    context: dict | None = None
    meta: dict | None = None


class RecommendationReason(BaseModel):
    code: str
    text: str


class RecommendationItem(BaseModel):
    product_id: str
    partner_id: str
    title: str
    price: Decimal | None = None
    discount: Decimal | None = None
    final_price: Decimal | None = None
    score: Decimal
    reasons: list[RecommendationReason] = Field(default_factory=list)
    badges: list[str] = Field(default_factory=list)
    valid_to: datetime | None = None


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem] = Field(default_factory=list)
    generated_at: datetime
    model: str


class RelatedProductsResponse(BaseModel):
    items: list[ProductListOut] = Field(default_factory=list)

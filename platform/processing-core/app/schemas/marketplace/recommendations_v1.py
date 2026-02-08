from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RecommendationPrice(BaseModel):
    currency: str
    model: str
    amount: Decimal | None = None


class RecommendationPreview(BaseModel):
    image_url: str | None = None
    short: str | None = None


class RecommendationItem(BaseModel):
    offer_id: str
    title: str
    subject_type: str
    price: RecommendationPrice | None = None
    partner_id: str
    category: str | None = None
    preview: RecommendationPreview | None = None
    reason_hint: str | None = None


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem] = Field(default_factory=list)
    generated_at: datetime
    ttl_seconds: int


class RecommendationWhyReason(BaseModel):
    code: str
    label: str
    evidence: dict | None = None


class RecommendationScoreBreakdown(BaseModel):
    signal: str
    value: int


class RecommendationWhyResponse(BaseModel):
    offer_id: str
    reasons: list[RecommendationWhyReason] = Field(default_factory=list)
    score_breakdown: list[RecommendationScoreBreakdown] = Field(default_factory=list)

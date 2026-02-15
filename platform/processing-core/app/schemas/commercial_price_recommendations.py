from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class RecommendationAction(str, Enum):
    HOLD = "HOLD"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DISABLE_STATION = "DISABLE_STATION"


class RecommendationStatus(str, Enum):
    DRAFT = "DRAFT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class PriceRecommendationItem(BaseModel):
    id: str
    created_at: datetime
    station_id: str
    station_name: str | None = None
    station_address: str | None = None
    risk_zone: str | None = None
    health_status: str | None = None
    product_code: str
    current_price: float
    recommended_price: float
    delta_price: float
    action: RecommendationAction
    confidence: float
    reasons: list[str]
    expected_volume_change_pct: float | None = None
    expected_margin_change: float | None = None
    policy_version: str
    status: RecommendationStatus


class PriceRecommendationListResponse(BaseModel):
    date_from: date
    date_to: date
    limit: int
    items: list[PriceRecommendationItem]


class PriceRecommendationStatusResponse(BaseModel):
    id: str
    status: RecommendationStatus

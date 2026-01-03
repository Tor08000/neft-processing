from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PromotionType = Literal[
    "PRODUCT_DISCOUNT",
    "CATEGORY_DISCOUNT",
    "PARTNER_STORE_DISCOUNT",
    "COUPON_PROMO",
]

PromotionStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED", "ARCHIVED"]


class PromotionCreate(BaseModel):
    promo_type: PromotionType
    title: str
    description: str | None = None
    scope: dict = Field(..., alias="scope_json")
    eligibility: dict | None = Field(default=None, alias="eligibility_json")
    rules: dict = Field(..., alias="rules_json")
    schedule: dict | None = Field(default=None, alias="schedule_json")
    limits: dict | None = Field(default=None, alias="limits_json")

    class Config:
        allow_population_by_field_name = True


class PromotionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    scope: dict | None = Field(default=None, alias="scope_json")
    eligibility: dict | None = Field(default=None, alias="eligibility_json")
    rules: dict | None = Field(default=None, alias="rules_json")
    schedule: dict | None = Field(default=None, alias="schedule_json")
    limits: dict | None = Field(default=None, alias="limits_json")

    class Config:
        allow_population_by_field_name = True


class PromotionOut(BaseModel):
    id: str
    tenant_id: str | None = None
    partner_id: str
    promo_type: PromotionType
    status: PromotionStatus
    title: str
    description: str | None = None
    scope_json: dict
    eligibility_json: dict | None = None
    rules_json: dict
    schedule_json: dict | None = None
    limits_json: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class PromotionListResponse(BaseModel):
    items: list[PromotionOut]
    total: int
    limit: int
    offset: int

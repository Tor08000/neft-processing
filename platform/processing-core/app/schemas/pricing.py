from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PriceVersionCreate(BaseModel):
    name: str
    notes: str | None = None


class PriceVersionOut(BaseModel):
    id: str
    name: str
    status: str
    notes: str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None
    activated_at: datetime | None = None


class PriceVersionItemIn(BaseModel):
    plan_code: str
    billing_period: str
    currency: str
    base_price: str
    setup_fee: str | None = None
    meta: dict[str, Any] | None = None


class PriceVersionItemOut(PriceVersionItemIn):
    id: int


class PriceScheduleCreate(BaseModel):
    price_version_id: str
    effective_from: datetime
    effective_to: datetime | None = None
    priority: int = 0


class PriceScheduleOut(BaseModel):
    id: str
    price_version_id: str
    effective_from: datetime
    effective_to: datetime | None = None
    priority: int
    status: str
    created_at: datetime | None = None


class PriceScheduleActivateNow(BaseModel):
    effective_from: datetime | None = Field(default=None)


class PriceRollbackIn(BaseModel):
    schedule_id: str


__all__ = [
    "PriceScheduleActivateNow",
    "PriceScheduleCreate",
    "PriceScheduleOut",
    "PriceVersionCreate",
    "PriceVersionItemIn",
    "PriceVersionItemOut",
    "PriceVersionOut",
    "PriceRollbackIn",
]

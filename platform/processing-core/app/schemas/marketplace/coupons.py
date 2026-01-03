from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CouponBatchType = Literal["PUBLIC", "TARGETED"]
CouponStatus = Literal["NEW", "ISSUED", "REDEEMED", "EXPIRED", "CANCELED"]


class CouponBatchCreate(BaseModel):
    promotion_id: str
    batch_type: CouponBatchType
    total_count: int = Field(..., ge=1, le=100000)
    code_prefix: str | None = None
    expires_at: datetime | None = None
    meta_json: dict | None = None


class CouponBatchOut(BaseModel):
    id: str
    tenant_id: str | None = None
    partner_id: str
    promotion_id: str
    batch_type: CouponBatchType
    code_prefix: str | None = None
    total_count: int
    issued_count: int
    redeemed_count: int
    meta_json: dict | None = None
    created_at: datetime
    updated_at: datetime | None = None


class CouponOut(BaseModel):
    id: str
    tenant_id: str | None = None
    batch_id: str
    promotion_id: str
    code: str
    status: CouponStatus
    client_id: str | None = None
    redeemed_order_id: str | None = None
    expires_at: datetime | None = None
    issued_at: datetime | None = None
    redeemed_at: datetime | None = None
    created_at: datetime


class CouponBatchListResponse(BaseModel):
    items: list[CouponBatchOut]
    total: int
    limit: int
    offset: int


class CouponIssueRequest(BaseModel):
    batch_id: str
    client_id: str


class CouponIssueResponse(BaseModel):
    coupon: CouponOut

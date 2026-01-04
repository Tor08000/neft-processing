from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OrderStatus = Literal[
    "CREATED",
    "ACCEPTED",
    "REJECTED",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]

OrderEventType = Literal[
    "ORDER_CREATED",
    "ORDER_ACCEPTED",
    "ORDER_REJECTED",
    "ORDER_STARTED",
    "ORDER_PROGRESS_UPDATED",
    "ORDER_COMPLETED",
    "ORDER_FAILED",
    "ORDER_CANCELLED",
    "ORDER_NOTE_ADDED",
]

OrderActorType = Literal["client", "partner", "admin", "system"]


class OrderCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_id: str
    quantity: Decimal = Field(..., gt=0)
    note: str | None = None
    external_ref: str | None = Field(default=None, alias="idempotency_key")
    promotion_id: str | None = None
    coupon_code: str | None = None


class OrderCancelRequest(BaseModel):
    reason: str


class OrderAcceptRequest(BaseModel):
    note: str | None = None


class OrderRejectRequest(BaseModel):
    reason: str


class OrderStartRequest(BaseModel):
    note: str | None = None


class OrderProgressUpdateRequest(BaseModel):
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    message: str | None = None


class OrderCompleteRequest(BaseModel):
    summary: str


class OrderFailRequest(BaseModel):
    reason: str


class OrderEventOut(BaseModel):
    id: str
    order_id: str
    event_type: OrderEventType
    occurred_at: datetime
    payload_redacted: dict
    actor_type: OrderActorType
    actor_id: str | None = None
    audit_event_id: str
    created_at: datetime


class OrderOut(BaseModel):
    id: str
    client_id: str
    partner_id: str
    product_id: str
    quantity: Decimal
    price_snapshot: dict
    price_snapshot_json: dict | None = None
    pricing_version: str | None = None
    applied_promotions_json: dict | None = None
    coupon_code_used: str | None = None
    status: OrderStatus
    created_at: datetime
    updated_at: datetime | None = None
    audit_event_id: str | None = None
    external_ref: str | None = None


class OrderDetailOut(OrderOut):
    events: list[OrderEventOut] = Field(default_factory=list)

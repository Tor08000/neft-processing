from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PaymentStatus = Literal["UNPAID", "AUTHORIZED", "PAID", "FAILED", "REFUNDED"]
PaymentMethod = Literal["NEFT_INTERNAL", "EXTERNAL_STUB"]

OrderStatus = Literal[
    "CREATED",
    "PENDING_PAYMENT",
    "PAID",
    "CONFIRMED_BY_PARTNER",
    "IN_PROGRESS",
    "COMPLETED",
    "CLOSED",
    "DECLINED_BY_PARTNER",
    "CANCELED_BY_CLIENT",
    "PAYMENT_FAILED",
    "ACCEPTED",
    "REJECTED",
    "FAILED",
    "CANCELLED",
]

OrderEventType = Literal[
    "CREATED",
    "PAYMENT_PENDING",
    "PAYMENT_PAID",
    "PAYMENT_FAILED",
    "CONFIRMED",
    "DECLINED",
    "COMPLETED",
    "CANCELED",
    "NOTE",
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

OrderLineSubjectType = Literal["PRODUCT", "SERVICE"]
OrderProofKind = Literal["PHOTO", "PDF", "ACT", "CHECK", "OTHER"]


class OrderLineIn(BaseModel):
    offer_id: str
    qty: Decimal = Field(..., gt=0)


class OrderCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[OrderLineIn]
    payment_method: PaymentMethod


class OrderPayRequest(BaseModel):
    payment_method: PaymentMethod


class OrderDeclineRequest(BaseModel):
    reason_code: str
    comment: str


class OrderCompleteRequest(BaseModel):
    comment: str | None = None


class OrderCancelRequest(BaseModel):
    reason: str | None = None


class ProofCreateRequest(BaseModel):
    attachment_id: str
    kind: OrderProofKind
    note: str | None = None


class OrderLineOut(BaseModel):
    id: str
    order_id: str
    offer_id: str
    subject_type: OrderLineSubjectType
    subject_id: str
    title_snapshot: str
    qty: Decimal
    unit_price: Decimal
    line_amount: Decimal
    meta: dict | None = None


class OrderProofOut(BaseModel):
    id: str
    order_id: str
    kind: OrderProofKind
    attachment_id: str
    note: str | None = None
    created_at: datetime
    meta: dict | None = None


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
    before_status: OrderStatus | None = None
    after_status: OrderStatus | None = None
    reason_code: str | None = None
    comment: str | None = None
    meta: dict | None = None


class OrderOut(BaseModel):
    id: str
    client_id: str
    partner_id: str
    status: OrderStatus
    payment_status: PaymentStatus | None = None
    payment_method: PaymentMethod | None = None
    currency: str | None = None
    subtotal_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    total_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime | None = None
    audit_event_id: str | None = None
    external_ref: str | None = None


class OrderDetailOut(OrderOut):
    lines: list[OrderLineOut] = Field(default_factory=list)
    proofs: list[OrderProofOut] = Field(default_factory=list)
    events: list[OrderEventOut] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int

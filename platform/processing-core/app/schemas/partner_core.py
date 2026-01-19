from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PartnerProfileOut(BaseModel):
    id: str
    org_id: int
    status: str
    display_name: str | None = None
    contacts_json: dict[str, Any] | None = None
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class PartnerProfileUpdate(BaseModel):
    display_name: str | None = None
    contacts_json: dict[str, Any] | None = None


class PartnerOfferIn(BaseModel):
    code: str
    title: str
    description: str | None = None
    base_price: Decimal | None = None
    currency: str = Field(default="RUB")
    status: str | None = None


class PartnerOfferUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    base_price: Decimal | None = None
    currency: str | None = None
    status: str | None = None


class PartnerOfferOut(BaseModel):
    id: str
    org_id: int
    code: str
    title: str
    description: str | None = None
    base_price: Decimal | None = None
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class PartnerOrderOut(BaseModel):
    id: str
    partner_org_id: int
    client_org_id: int | None = None
    offer_id: str | None = None
    title: str
    status: str
    response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PartnerOrderListResponse(BaseModel):
    items: list[PartnerOrderOut]
    next_cursor: str | None = None


class PartnerOrderStatusUpdate(BaseModel):
    status: str


class PartnerOrderSeedIn(BaseModel):
    partner_org_id: int
    client_org_id: int | None = None
    offer_id: str | None = None
    title: str
    response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None


class PartnerAnalyticsSummary(BaseModel):
    orders_total: int
    orders_by_status: dict[str, int]
    sla_breaches_count: int
    last_10_activity: list[dict[str, Any]] | None = None


__all__ = [
    "PartnerAnalyticsSummary",
    "PartnerOfferIn",
    "PartnerOfferOut",
    "PartnerOfferUpdate",
    "PartnerOrderListResponse",
    "PartnerOrderOut",
    "PartnerOrderSeedIn",
    "PartnerOrderStatusUpdate",
    "PartnerProfileOut",
    "PartnerProfileUpdate",
]

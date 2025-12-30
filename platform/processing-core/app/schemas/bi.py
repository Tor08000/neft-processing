from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.bi import BiExportFormat, BiExportKind, BiExportStatus, BiScopeType


class BiDailyMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    date: date
    scope_type: BiScopeType
    scope_id: str
    spend_total: int
    orders_total: int
    orders_completed: int
    refunds_total: int
    payouts_total: int
    declines_total: int
    top_primary_reason: str | None = None
    updated_at: datetime | None = None


class BiOrderEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    client_id: str | None
    partner_id: str | None
    order_id: str | None
    event_id: str
    event_type: str
    occurred_at: datetime
    amount: int | None
    currency: str | None
    service_id: str | None
    offer_id: str | None
    status_after: str | None


class BiPayoutEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    partner_id: str | None
    settlement_id: str | None
    payout_batch_id: str | None
    event_type: str
    occurred_at: datetime
    amount_gross: int | None
    amount_net: int | None
    amount_commission: int | None
    currency: str | None


class BiDeclineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    client_id: str | None
    partner_id: str | None
    operation_id: str
    occurred_at: datetime
    primary_reason: str | None
    amount: int | None
    product_type: str | None
    station_id: str | None


class BiExportCreateRequest(BaseModel):
    kind: BiExportKind
    scope_type: BiScopeType | None = None
    scope_id: str | None = None
    date_from: date
    date_to: date
    format: BiExportFormat = BiExportFormat.CSV


class BiExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: int
    kind: BiExportKind
    scope_type: BiScopeType | None
    scope_id: str | None
    date_from: date
    date_to: date
    format: BiExportFormat
    status: BiExportStatus
    object_key: str | None
    bucket: str | None
    sha256: str | None
    row_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None = None
    delivered_at: datetime | None = None
    confirmed_at: datetime | None = None


class BiTopReasonOut(BaseModel):
    primary_reason: str
    count: int


__all__ = [
    "BiDailyMetricOut",
    "BiDeclineEventOut",
    "BiExportCreateRequest",
    "BiExportOut",
    "BiOrderEventOut",
    "BiPayoutEventOut",
    "BiTopReasonOut",
]

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.settlement_v1 import (
    PayoutStatus,
    SettlementItemDirection,
    SettlementItemSourceType,
    SettlementPeriodStatus,
)


class SettlementPeriodCalculateRequest(BaseModel):
    partner_id: str
    currency: str
    period_start: datetime
    period_end: datetime
    idempotency_key: str


class SettlementPeriodPayoutRequest(BaseModel):
    provider: str = "bank_stub"
    idempotency_key: str


class SettlementItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: SettlementItemSourceType
    source_id: str
    amount: Decimal
    direction: SettlementItemDirection
    created_at: datetime


class SettlementPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    partner_id: str
    currency: str
    period_start: datetime
    period_end: datetime
    status: SettlementPeriodStatus
    total_gross: Decimal
    total_fees: Decimal
    total_refunds: Decimal
    net_amount: Decimal
    created_at: datetime
    approved_at: datetime | None
    paid_at: datetime | None
    audit_event_id: str | None
    items: list[SettlementItemOut] | None = None


class SettlementPeriodListResponse(BaseModel):
    items: list[SettlementPeriodOut]
    total: int


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    settlement_period_id: str
    partner_id: str
    currency: str
    amount: Decimal
    status: PayoutStatus
    provider: str
    provider_payout_id: str | None
    idempotency_key: str
    ledger_tx_id: str | None
    audit_event_id: str | None
    created_at: datetime


class PayoutListResponse(BaseModel):
    items: list[PayoutOut]
    total: int

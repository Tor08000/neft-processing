from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SettlementOut(BaseModel):
    id: UUID
    merchant_id: str
    partner_id: str | None = None
    period_from: date
    period_to: date
    currency: str
    total_amount: int
    commission_amount: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayoutEventOut(BaseModel):
    id: UUID
    event_type: str
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayoutOrderOut(BaseModel):
    id: UUID
    settlement_id: UUID
    amount: int
    currency: str
    status: str
    provider_ref: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    events: list[PayoutEventOut] | None = None

    model_config = ConfigDict(from_attributes=True)


class PartnerBalanceItem(BaseModel):
    currency: str
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class PartnerBalanceResponse(BaseModel):
    partner_id: str
    balances: list[PartnerBalanceItem]

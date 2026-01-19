from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PartnerBalanceOut(BaseModel):
    partner_org_id: str
    currency: str
    balance_available: Decimal
    balance_pending: Decimal
    balance_blocked: Decimal


class PartnerLedgerEntryOut(BaseModel):
    id: str
    partner_org_id: str
    order_id: str | None = None
    entry_type: str
    amount: Decimal
    currency: str
    direction: str
    meta_json: dict | None = None
    created_at: datetime


class PartnerLedgerListResponse(BaseModel):
    items: list[PartnerLedgerEntryOut]


class PartnerPayoutRequestIn(BaseModel):
    amount: Decimal
    currency: str = Field(default="RUB")


class PartnerPayoutRequestOut(BaseModel):
    id: str
    partner_org_id: str
    amount: Decimal
    currency: str
    status: str
    requested_by: str | None = None
    approved_by: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class PartnerPayoutListResponse(BaseModel):
    items: list[PartnerPayoutRequestOut]


class PartnerDocumentOut(BaseModel):
    id: str
    partner_org_id: str
    period_from: date
    period_to: date
    total_amount: Decimal
    currency: str
    status: str
    tax_context: dict | None = None
    pdf_object_key: str | None = None
    created_at: datetime


class PartnerDocumentListResponse(BaseModel):
    items: list[PartnerDocumentOut]


class PartnerPayoutPreviewOut(BaseModel):
    partner_org_id: str
    currency: str
    available_amount: Decimal
    min_payout_amount: Decimal | None = None
    payout_hold_days: int | None = None
    payout_schedule: str | None = None
    payout_block_reasons: list[str] = []
    legal_status: str | None = None
    tax_context: dict | None = None
    warnings: list[str] = []

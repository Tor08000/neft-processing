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


class PartnerLedgerEntrySummary(BaseModel):
    ts: datetime
    type: str
    amount: Decimal
    ref_id: str | None = None
    correlation_id: str | None = None
    description: str | None = None


class PartnerLedgerListResponse(BaseModel):
    items: list[PartnerLedgerEntryOut] | None = None
    entries: list[PartnerLedgerEntrySummary] | None = None
    cursor: str | None = None
    total: int | None = None
    totals: dict[str, Decimal] | None = None


class PartnerPayoutRequestIn(BaseModel):
    amount: Decimal | None = None
    currency: str = Field(default="RUB")


class PartnerPayoutRequestOut(BaseModel):
    id: str
    partner_org_id: str
    amount: Decimal
    currency: str
    status: str
    correlation_id: str | None = None
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
    available_to_withdraw: Decimal | None = None
    min_payout_amount: Decimal | None = None
    payout_hold_days: int | None = None
    payout_schedule: str | None = None
    payout_block_reasons: list[str] = []
    holds: list[str] = []
    penalties: list[str] = []
    block_reason: str | None = None
    next_payout_date: datetime | None = None
    legal_status: str | None = None
    tax_context: dict | None = None
    warnings: list[str] = []


class PartnerDashboardBlockedPayouts(BaseModel):
    total: int
    reasons: dict[str, int]


class PartnerDashboardSlaPenalties(BaseModel):
    count: int
    total_amount: Decimal


class PartnerDashboardLegalSummary(BaseModel):
    status: str | None = None
    required_enabled: bool | None = None
    block_reason: str | None = None


class PartnerDashboardSummary(BaseModel):
    balance: Decimal
    pending: Decimal
    blocked: Decimal
    currency: str
    blocked_payouts: PartnerDashboardBlockedPayouts
    sla_penalties: PartnerDashboardSlaPenalties
    legal: PartnerDashboardLegalSummary


class PartnerPayoutHistoryItem(BaseModel):
    id: str
    status: str
    amount: Decimal
    created_at: datetime
    approved_at: datetime | None = None
    paid_at: datetime | None = None
    block_reason: str | None = None
    correlation_id: str | None = None


class PartnerPayoutHistoryResponse(BaseModel):
    requests: list[PartnerPayoutHistoryItem]


class PartnerDocSummary(BaseModel):
    id: str
    doc_type: str
    period_from: date | None = None
    period_to: date | None = None
    total_amount: Decimal | None = None
    currency: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    download_url: str | None = None


class PartnerDocsResponse(BaseModel):
    items: list[PartnerDocSummary]

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.finance import CreditNoteStatus, PaymentStatus
from app.models.invoice import InvoiceStatus


class PaymentRequest(BaseModel):
    invoice_id: str
    amount: int = Field(..., gt=0)
    currency: str = "RUB"
    idempotency_key: str | None = None


class PaymentResponse(BaseModel):
    payment_id: str
    invoice_id: str
    amount: int
    currency: str
    due_amount: int
    invoice_status: InvoiceStatus
    status: PaymentStatus
    created_at: datetime


class CreditNoteRequest(BaseModel):
    invoice_id: str
    amount: int = Field(..., gt=0)
    currency: str = "RUB"
    reason: str | None = None
    idempotency_key: str | None = None


class CreditNoteResponse(BaseModel):
    credit_note_id: str
    invoice_id: str
    amount: int
    currency: str
    due_amount: int
    invoice_status: InvoiceStatus
    status: CreditNoteStatus
    created_at: datetime


class WriteActionRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    idempotency_key: str | None = None


class FinanceOverviewBlockedReason(BaseModel):
    reason: str
    count: int


class FinanceOverviewResponse(BaseModel):
    window: Literal["24h", "7d"]
    overdue_orgs: int
    overdue_amount: Decimal
    invoices_issued_24h: int
    invoices_paid_24h: int
    payment_intakes_pending: int
    reconciliation_unmatched_24h: int
    payout_queue_pending: int
    payout_blocked_top_reasons: list[FinanceOverviewBlockedReason]
    mor_immutable_violations_24h: int
    clawback_required_24h: int


class AdminInvoiceSummary(BaseModel):
    id: str
    org_id: str | None = None
    subscription_id: str | None = None
    status: str
    period_start: date | None = None
    period_end: date | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    total: Decimal | None = None
    currency: str | None = None


class AdminInvoiceDetail(AdminInvoiceSummary):
    pdf_url: str | None = None


class AdminInvoiceListResponse(BaseModel):
    items: list[AdminInvoiceSummary]
    total: int
    limit: int
    offset: int


class AdminInvoiceActionResponse(BaseModel):
    invoice: AdminInvoiceDetail
    correlation_id: str | None = None


class AdminPaymentIntakeDetail(BaseModel):
    id: int
    org_id: int
    invoice_id: int
    status: str
    amount: Decimal
    currency: str
    payer_name: str | None = None
    payer_inn: str | None = None
    bank_reference: str | None = None
    paid_at_claimed: date | None = None
    comment: str | None = None
    proof: dict | None = None
    proof_url: str | None = None
    created_by_user_id: str | None = None
    reviewed_by_admin: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime | None = None
    invoice_link: str | None = None


class AdminPaymentIntakeListResponse(BaseModel):
    items: list[AdminPaymentIntakeDetail]
    total: int
    limit: int
    offset: int


class AdminPaymentIntakeActionResponse(BaseModel):
    intake: AdminPaymentIntakeDetail
    correlation_id: str | None = None


class PayoutQueueItem(BaseModel):
    payout_id: str
    partner_org: str
    amount: Decimal
    currency: str
    status: str
    blockers: list[str]
    created_at: datetime | None = None


class PayoutQueueListResponse(BaseModel):
    items: list[PayoutQueueItem]
    total: int
    limit: int
    offset: int


class PayoutPolicyInfo(BaseModel):
    min_payout_amount: Decimal | None = None
    payout_hold_days: int | None = None
    payout_schedule: str | None = None


class PayoutTraceItem(BaseModel):
    entity_type: str
    entity_id: str
    amount: Decimal | None = None
    currency: str | None = None
    created_at: datetime | None = None


class PayoutDetail(PayoutQueueItem):
    processed_at: datetime | None = None
    policy: PayoutPolicyInfo | None = None
    trace: list[PayoutTraceItem] = []
    totals: dict[str, Decimal] | None = None
    legal_status: str | None = None


class PayoutActionResponse(BaseModel):
    payout: PayoutDetail
    correlation_id: str | None = None

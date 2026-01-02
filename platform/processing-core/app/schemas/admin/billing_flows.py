from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.billing_flow import (
    BillingInvoiceStatus,
    BillingPaymentStatus,
    BillingRefundStatus,
)


class BillingInvoiceIssueRequest(BaseModel):
    client_id: str
    case_id: str | None = None
    currency: str
    amount_total: Decimal = Field(..., gt=0)
    due_at: datetime | None = None
    idempotency_key: str


class BillingInvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    client_id: str
    case_id: str | None
    currency: str
    amount_total: Decimal
    amount_paid: Decimal
    status: BillingInvoiceStatus
    issued_at: datetime
    due_at: datetime | None
    ledger_tx_id: str
    audit_event_id: str
    created_at: datetime


class BillingInvoiceListResponse(BaseModel):
    items: list[BillingInvoiceResponse]
    total: int
    limit: int
    offset: int


class BillingPaymentCaptureRequest(BaseModel):
    provider: str
    provider_payment_id: str | None = None
    amount: Decimal = Field(..., gt=0)
    currency: str
    idempotency_key: str


class BillingPaymentResponse(BaseModel):
    id: str
    invoice_id: str
    provider: str
    provider_payment_id: str | None
    currency: str
    amount: Decimal
    captured_at: datetime
    status: BillingPaymentStatus
    ledger_tx_id: str
    audit_event_id: str
    created_at: datetime


class BillingPaymentsListResponse(BaseModel):
    items: list[BillingPaymentResponse]
    total: int
    limit: int
    offset: int


class BillingRefundRequest(BaseModel):
    provider_refund_id: str | None = None
    amount: Decimal = Field(..., gt=0)
    currency: str
    idempotency_key: str


class BillingRefundResponse(BaseModel):
    id: str
    payment_id: str
    provider_refund_id: str | None
    currency: str
    amount: Decimal
    refunded_at: datetime
    status: BillingRefundStatus
    ledger_tx_id: str
    audit_event_id: str
    created_at: datetime


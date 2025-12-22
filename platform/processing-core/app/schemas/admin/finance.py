from __future__ import annotations

from datetime import datetime

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

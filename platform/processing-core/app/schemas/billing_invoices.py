from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ClosePeriodRequest(BaseModel):
    date_from: date
    date_to: date
    tenant_id: int


class ClosePeriodResponse(BaseModel):
    batch_id: str
    txn_count: int
    total_amount: int
    total_qty: Decimal | None = None


class InvoiceGenerateResponse(BaseModel):
    invoice_id: str
    state: str
    pdf_url: str | None = None


class InvoiceOut(BaseModel):
    id: str
    batch_id: str | None = None
    number: str | None = None
    amount: int
    vat: int
    state: str
    pdf_url: str | None = None
    pdf_object_key: str | None = None
    issued_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoicePaymentRequest(BaseModel):
    amount: int = Field(..., gt=0)
    external_ref: str = Field(..., min_length=1, max_length=128)
    provider: str | None = Field(default=None, max_length=64)


class InvoicePaymentResponse(BaseModel):
    payment_id: str
    invoice_id: str
    amount: int
    currency: str
    due_amount: int
    invoice_status: str
    status: str

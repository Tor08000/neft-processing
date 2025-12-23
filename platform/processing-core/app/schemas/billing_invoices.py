from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ClosePeriodRequest(BaseModel):
    from_date: date = Field(..., alias="from")
    to_date: date = Field(..., alias="to")
    tenant_id: int

    model_config = ConfigDict(populate_by_name=True)


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

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.billing_payment_intakes import PaymentIntakeOut

InvoiceId = str | int
SubscriptionId = str | int


class SubscriptionInvoiceLineOut(BaseModel):
    line_type: str
    ref_code: str | None = None
    description: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class SubscriptionInvoiceOut(BaseModel):
    id: InvoiceId
    org_id: int
    subscription_id: SubscriptionId | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str
    issued_at: datetime | None = None
    due_at: datetime | None = None
    suspend_at: datetime | None = None
    subscription_status: str | None = None
    paid_at: datetime | None = None
    total_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    amount_refunded: Decimal | None = None
    amount_due: Decimal | None = None
    currency: str | None = None
    pdf_object_key: str | None = None
    download_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionInvoiceDetailOut(SubscriptionInvoiceOut):
    lines: list[SubscriptionInvoiceLineOut] = []
    payment_intakes: list[PaymentIntakeOut] = []


class SubscriptionInvoiceListResponse(BaseModel):
    items: list[SubscriptionInvoiceOut]
    total: int


class SubscriptionInvoiceGenerateRequest(BaseModel):
    org_id: int | None = None
    subscription_id: int | None = None
    target_date: date | None = None


class SubscriptionInvoiceGenerateResponse(BaseModel):
    invoice_ids: list[InvoiceId]
    created: int


class SubscriptionInvoiceStatusResponse(BaseModel):
    id: InvoiceId
    status: str
    paid_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

InvoiceId = str | int


class BillingPaymentIntakeStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PaymentIntakeAttachmentIn(BaseModel):
    file_name: str
    content_type: str
    size: int


class PaymentIntakeAttachmentOut(PaymentIntakeAttachmentIn):
    object_key: str


class PaymentIntakeAttachmentInitResponse(BaseModel):
    upload_url: str
    object_key: str


class PaymentIntakeCreateRequest(BaseModel):
    amount: Decimal
    currency: str
    paid_at_claimed: date | None = None
    bank_reference: str | None = None
    payer_name: str | None = None
    payer_inn: str | None = None
    comment: str | None = None
    proof: PaymentIntakeAttachmentOut | None = None


class PaymentIntakeOut(BaseModel):
    id: int
    org_id: int
    invoice_id: InvoiceId
    status: BillingPaymentIntakeStatus
    amount: Decimal
    currency: str
    payer_name: str | None = None
    payer_inn: str | None = None
    bank_reference: str | None = None
    paid_at_claimed: date | None = None
    comment: str | None = None
    proof: PaymentIntakeAttachmentOut | None = None
    proof_url: str | None = None
    created_by_user_id: str
    reviewed_by_admin: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentIntakeListResponse(BaseModel):
    items: list[PaymentIntakeOut]
    total: int
    limit: int
    offset: int


class PaymentIntakeApproveRequest(BaseModel):
    review_note: str | None = None


class PaymentIntakeRejectRequest(BaseModel):
    review_note: str = Field(..., min_length=1)


class ClientPaymentIntakeRequest(BaseModel):
    invoice_id: InvoiceId
    amount: Decimal = Field(..., gt=0)
    method: str = Field(..., min_length=1, max_length=64)
    reference: str | None = None
    attachment: str | None = None

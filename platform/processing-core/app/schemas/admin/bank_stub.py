from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.bank_stub import BankStubPaymentStatus


class BankStubPaymentCreateRequest(BaseModel):
    invoice_id: str
    amount: Decimal | None = None
    idempotency_key: str | None = None


class BankStubPaymentResponse(BaseModel):
    id: str
    tenant_id: int
    invoice_id: str
    payment_ref: str
    amount: Decimal
    currency: str
    status: BankStubPaymentStatus
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankStubStatementLineResponse(BaseModel):
    payment_ref: str
    invoice_number: str | None
    amount: Decimal
    currency: str
    posted_at: datetime
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class BankStubStatementResponse(BaseModel):
    id: str
    tenant_id: int
    period_from: datetime
    period_to: datetime
    checksum: str
    payload: dict | None = None
    created_at: datetime
    lines: list[BankStubStatementLineResponse]

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "BankStubPaymentCreateRequest",
    "BankStubPaymentResponse",
    "BankStubStatementLineResponse",
    "BankStubStatementResponse",
]

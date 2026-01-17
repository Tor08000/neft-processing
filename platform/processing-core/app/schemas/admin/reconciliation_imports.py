from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BankStatementImportCreateRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=128)
    size_bytes: int = Field(..., ge=1)
    format: Literal["CSV", "CLIENT_BANK_1C", "MT940"]
    period_from: date | None = None
    period_to: date | None = None


class BankStatementImportCreateResponse(BaseModel):
    import_id: str
    upload_url: str
    object_key: str


class BankStatementImportCompleteRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=512)


class BankStatementImportRead(BaseModel):
    id: str
    uploaded_by_admin: str | None
    uploaded_at: datetime
    file_object_key: str
    format: str
    period_from: date | None
    period_to: date | None
    status: str
    error: str | None

    model_config = ConfigDict(from_attributes=True)


class BankStatementImportListResponse(BaseModel):
    items: list[BankStatementImportRead]


class BankStatementTransactionRead(BaseModel):
    id: str
    import_id: str
    bank_tx_id: str
    posted_at: datetime
    amount: Decimal
    currency: str
    payer_name: str | None
    payer_inn: str | None
    reference: str | None
    purpose_text: str | None
    raw_json: dict[str, Any] | None
    matched_status: str
    matched_invoice_id: str | None
    confidence_score: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankStatementTransactionListResponse(BaseModel):
    items: list[BankStatementTransactionRead]


class BankStatementTransactionApplyRequest(BaseModel):
    invoice_id: str = Field(..., min_length=1, max_length=36)

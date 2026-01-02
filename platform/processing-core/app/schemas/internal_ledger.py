from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)


class InternalLedgerEntryInput(BaseModel):
    account_type: InternalLedgerAccountType
    client_id: str | None = None
    direction: InternalLedgerEntryDirection
    amount: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    meta: dict[str, object] | None = None


class InternalLedgerTransactionRequest(BaseModel):
    tenant_id: int = Field(..., ge=0)
    transaction_type: InternalLedgerTransactionType
    external_ref_type: str
    external_ref_id: str
    idempotency_key: str
    posted_at: datetime | None = None
    meta: dict[str, object] | None = None
    entries: list[InternalLedgerEntryInput]


class InternalLedgerEntryResponse(BaseModel):
    id: str
    ledger_transaction_id: str
    account_id: str
    direction: InternalLedgerEntryDirection
    amount: int
    currency: str
    entry_hash: str
    created_at: datetime
    meta: dict[str, object] | None = None


class InternalLedgerTransactionResponse(BaseModel):
    transaction_id: str
    transaction_type: InternalLedgerTransactionType
    external_ref_type: str
    external_ref_id: str
    idempotency_key: str
    total_amount: int | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    created_at: datetime
    is_replay: bool
    entries: list[InternalLedgerEntryResponse]

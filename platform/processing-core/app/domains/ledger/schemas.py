from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.ledger.enums import EntryType, LineDirection


class LedgerLineIn(BaseModel):
    account_code: str
    owner_id: UUID | None = None
    direction: LineDirection
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    memo: str | None = None


class LedgerPostRequest(BaseModel):
    entry_type: EntryType
    idempotency_key: str
    correlation_id: str
    narrative: str | None = None
    dimensions: dict = Field(default_factory=dict)
    lines: list[LedgerLineIn]


class LedgerLineOut(BaseModel):
    line_no: int
    account_id: UUID
    direction: LineDirection
    amount: Decimal
    currency: str


class LedgerEntryOut(BaseModel):
    entry_id: UUID
    status: str
    posted_at: datetime | None
    lines: list[LedgerLineOut]


class LedgerBalanceOut(BaseModel):
    account_id: UUID
    currency: str
    balance: Decimal

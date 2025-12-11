from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.account import AccountStatus, AccountType
from app.models.ledger_entry import LedgerDirection


class AccountBalanceSchema(BaseModel):
    id: int
    client_id: str
    card_id: Optional[str] = None
    tariff_id: Optional[str] = None
    currency: str
    type: AccountType
    status: AccountStatus
    balance: Decimal


class AccountsPage(BaseModel):
    items: List[AccountBalanceSchema]
    total: int


class LedgerEntrySchema(BaseModel):
    id: int
    operation_id: Optional[UUID]
    posted_at: datetime
    direction: LedgerDirection
    amount: Decimal
    currency: str
    balance_after: Optional[Decimal]


class StatementResponse(BaseModel):
    account_id: int
    entries: List[LedgerEntrySchema]

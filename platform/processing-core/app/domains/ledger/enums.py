from __future__ import annotations

from enum import Enum


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class OwnerType(str, Enum):
    PLATFORM = "PLATFORM"
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"
    MERCHANT = "MERCHANT"


class EntryStatus(str, Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class EntryType(str, Enum):
    CAPTURE = "CAPTURE"
    REVERSE = "REVERSE"
    PAYOUT = "PAYOUT"
    ADJUSTMENT = "ADJUSTMENT"


class LineDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

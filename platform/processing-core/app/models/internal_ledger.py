from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class InternalLedgerAccountType(str, Enum):
    CLIENT_AR = "CLIENT_AR"
    CLIENT_CASH = "CLIENT_CASH"
    PLATFORM_REVENUE = "PLATFORM_REVENUE"
    PLATFORM_FEES = "PLATFORM_FEES"
    TAX_VAT = "TAX_VAT"
    PROVIDER_PAYABLE = "PROVIDER_PAYABLE"
    SUSPENSE = "SUSPENSE"
    SETTLEMENT_CLEARING = "SETTLEMENT_CLEARING"
    PARTNER_SETTLEMENT = "PARTNER_SETTLEMENT"


class InternalLedgerAccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class InternalLedgerTransactionType(str, Enum):
    INVOICE_ISSUED = "INVOICE_ISSUED"
    PAYMENT_APPLIED = "PAYMENT_APPLIED"
    CREDIT_NOTE_APPLIED = "CREDIT_NOTE_APPLIED"
    REFUND_APPLIED = "REFUND_APPLIED"
    SETTLEMENT_ALLOCATION_CREATED = "SETTLEMENT_ALLOCATION_CREATED"
    ACCOUNTING_EXPORT_CONFIRMED = "ACCOUNTING_EXPORT_CONFIRMED"
    FUEL_SETTLEMENT = "FUEL_SETTLEMENT"
    FUEL_REVERSAL = "FUEL_REVERSAL"
    ADJUSTMENT = "ADJUSTMENT"
    PARTNER_PAYOUT = "PARTNER_PAYOUT"


class InternalLedgerEntryDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class InternalLedgerAccount(Base):
    __tablename__ = "internal_ledger_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "client_id",
            "account_type",
            "currency",
            name="uq_internal_ledger_accounts_scope",
        ),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=True)
    account_type = Column(
        ExistingEnum(InternalLedgerAccountType, name="internal_ledger_account_type"),
        nullable=False,
    )
    currency = Column(String(3), nullable=False)
    status = Column(
        ExistingEnum(InternalLedgerAccountStatus, name="internal_ledger_account_status"),
        nullable=False,
        default=InternalLedgerAccountStatus.ACTIVE,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InternalLedgerTransaction(Base):
    __tablename__ = "internal_ledger_transactions"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    transaction_type = Column(
        ExistingEnum(InternalLedgerTransactionType, name="internal_ledger_transaction_type"),
        nullable=False,
    )
    external_ref_type = Column(String(64), nullable=False)
    external_ref_id = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    total_amount = Column(BigInteger, nullable=True)
    currency = Column(String(3), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


class InternalLedgerEntry(Base):
    __tablename__ = "internal_ledger_entries"
    __table_args__ = (
        Index("ix_internal_ledger_entries_account_created", "account_id", "created_at"),
        Index("ix_internal_ledger_entries_transaction", "ledger_transaction_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    ledger_transaction_id = Column(
        GUID(),
        ForeignKey("internal_ledger_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id = Column(GUID(), ForeignKey("internal_ledger_accounts.id"), nullable=False)
    direction = Column(
        ExistingEnum(InternalLedgerEntryDirection, name="internal_ledger_entry_direction"),
        nullable=False,
    )
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    entry_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


__all__ = [
    "InternalLedgerAccount",
    "InternalLedgerAccountType",
    "InternalLedgerAccountStatus",
    "InternalLedgerTransaction",
    "InternalLedgerTransactionType",
    "InternalLedgerEntry",
    "InternalLedgerEntryDirection",
]

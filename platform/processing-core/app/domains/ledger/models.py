from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID, new_uuid_str


class LedgerAccountV1(Base):
    __tablename__ = "internal_ledger_v1_accounts"
    __table_args__ = (
        UniqueConstraint("account_code", "owner_type", "owner_id", "currency", name="uq_ilv1_accounts_scope"),
        Index("ix_ilv1_accounts_owner", "owner_type", "owner_id"),
        Index("ix_ilv1_accounts_currency", "currency"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    account_code = Column(Text, nullable=False)
    account_type = Column(String(16), nullable=False)
    owner_type = Column(String(16), nullable=False)
    owner_id = Column(GUID(), nullable=True)
    currency = Column(String(3), nullable=False, server_default="RUB")
    status = Column(String(16), nullable=False, server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LedgerEntryV1(Base):
    __tablename__ = "internal_ledger_v1_entries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ilv1_entries_idempotency"),
        Index("ix_ilv1_entries_correlation", "correlation_id"),
        Index("ix_ilv1_entries_dimensions", "dimensions", postgresql_using="gin"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    status = Column(String(16), nullable=False)
    entry_type = Column(String(32), nullable=False)
    idempotency_key = Column(Text, nullable=False)
    correlation_id = Column(Text, nullable=False)
    source_system = Column(Text, nullable=False, server_default="core-api")
    source_event_id = Column(Text, nullable=True)
    narrative = Column(Text, nullable=True)
    dimensions = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, server_default="{}")
    posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LedgerLineV1(Base):
    __tablename__ = "internal_ledger_v1_lines"
    __table_args__ = (
        UniqueConstraint("entry_id", "line_no", name="uq_ilv1_lines_entry_line_no"),
        CheckConstraint("amount > 0", name="ck_ilv1_lines_amount_positive"),
        Index("ix_ilv1_lines_entry", "entry_id"),
        Index("ix_ilv1_lines_account", "account_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    entry_id = Column(GUID(), ForeignKey("internal_ledger_v1_entries.id", ondelete="RESTRICT"), nullable=False)
    line_no = Column(Integer, nullable=False)
    account_id = Column(GUID(), ForeignKey("internal_ledger_v1_accounts.id", ondelete="RESTRICT"), nullable=False)
    direction = Column(String(8), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    memo = Column(Text, nullable=True)


class LedgerAccountBalanceV1(Base):
    __tablename__ = "internal_ledger_v1_account_balances"

    account_id = Column(GUID(), ForeignKey("internal_ledger_v1_accounts.id", ondelete="RESTRICT"), primary_key=True)
    currency = Column(String(3), primary_key=True)
    balance = Column(Numeric(18, 2), nullable=False, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

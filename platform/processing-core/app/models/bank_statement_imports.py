from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON, Numeric

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class BankStatementImportStatus(str, Enum):
    IMPORTED = "IMPORTED"
    PARSED = "PARSED"
    FAILED = "FAILED"


class BankStatementMatchStatus(str, Enum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    IGNORED = "IGNORED"


class BankStatementImport(Base):
    __tablename__ = "bank_statement_imports"
    __table_args__ = (Index("ix_bank_statement_imports_created", "uploaded_at"),)

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    uploaded_by_admin = Column(String(128), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    file_object_key = Column(Text, nullable=False)
    format = Column(String(32), nullable=False)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=True)
    status = Column(ExistingEnum(BankStatementImportStatus, name="bank_statement_import_status"), nullable=False)
    error = Column(Text, nullable=True)


class BankStatementTransaction(Base):
    __tablename__ = "bank_statement_transactions"
    __table_args__ = (
        UniqueConstraint("bank_tx_id", name="uq_bank_statement_transactions_tx_id"),
        Index("ix_bank_statement_transactions_import", "import_id"),
        Index("ix_bank_statement_transactions_status", "matched_status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    import_id = Column(GUID(), ForeignKey("bank_statement_imports.id", ondelete="CASCADE"), nullable=False)
    bank_tx_id = Column(String(128), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(8), nullable=False)
    payer_name = Column(String(255), nullable=True)
    payer_inn = Column(String(32), nullable=True)
    reference = Column(String(128), nullable=True)
    purpose_text = Column(Text, nullable=True)
    raw_json = Column(JSON_TYPE, nullable=True)
    matched_status = Column(
        ExistingEnum(BankStatementMatchStatus, name="bank_statement_match_status"),
        nullable=False,
    )
    matched_invoice_id = Column(String(36), nullable=True)
    confidence_score = Column(Numeric(5, 2), nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "BankStatementImport",
    "BankStatementImportStatus",
    "BankStatementMatchStatus",
    "BankStatementTransaction",
]

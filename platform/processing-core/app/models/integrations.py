from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    BigInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON, Numeric

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class IntegrationType(str, Enum):
    ONEC = "ONEC"
    BANK = "BANK"


class IntegrationExportStatus(str, Enum):
    CREATED = "CREATED"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


class BankStatementStatus(str, Enum):
    IMPORTED = "IMPORTED"
    PARSED = "PARSED"
    FAILED = "FAILED"


class BankTransactionDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class ReconciliationRunStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReconciliationMatchType(str, Enum):
    EXACT_REF = "EXACT_REF"
    INN_AMOUNT_DATE = "INN_AMOUNT_DATE"
    FUZZY = "FUZZY"


class ReconciliationDiffSource(str, Enum):
    LEDGER = "LEDGER"
    BANK = "BANK"


class ReconciliationDiffReason(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    DUPLICATE_MATCH = "DUPLICATE_MATCH"
    COUNTERPARTY_MISMATCH = "COUNTERPARTY_MISMATCH"


class IntegrationMapping(Base):
    __tablename__ = "integration_mappings"
    __table_args__ = (
        Index("ix_integration_mappings_type_entity", "integration_type", "entity_type"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    integration_type = Column(ExistingEnum(IntegrationType, name="integration_type"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    source_field = Column(String(128), nullable=False)
    target_field = Column(String(128), nullable=False)
    transform = Column(String(128), nullable=True)
    is_required = Column(Boolean, nullable=False, server_default="false", default=False)
    version = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntegrationFile(Base):
    __tablename__ = "integration_files"
    __table_args__ = (
        Index("ix_integration_files_created", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    file_name = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    payload = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntegrationExport(Base):
    __tablename__ = "integration_exports"
    __table_args__ = (
        Index("ix_integration_exports_type_status", "integration_type", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    integration_type = Column(ExistingEnum(IntegrationType, name="integration_type"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(ExistingEnum(IntegrationExportStatus, name="integration_export_status"), nullable=False)
    file_id = Column(GUID(), ForeignKey("integration_files.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankStatement(Base):
    __tablename__ = "bank_statements"
    __table_args__ = (
        Index("ix_bank_statements_bank_period", "bank_code", "period_end"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    bank_code = Column(String(32), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    uploaded_by = Column(String(64), nullable=True)
    file_id = Column(GUID(), ForeignKey("integration_files.id"), nullable=True)
    status = Column(ExistingEnum(BankStatementStatus, name="bank_statement_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index("ix_bank_transactions_statement", "statement_id"),
        Index("ix_bank_transactions_hash", "hash"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    statement_id = Column(GUID(), ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(8), nullable=False)
    direction = Column(ExistingEnum(BankTransactionDirection, name="bank_transaction_direction"), nullable=False)
    counterparty = Column(String(255), nullable=True)
    purpose = Column(Text, nullable=True)
    external_ref = Column(String(128), nullable=True)
    hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankReconciliationRun(Base):
    __tablename__ = "bank_reconciliation_runs"
    __table_args__ = (
        Index("ix_bank_reconciliation_runs_statement", "statement_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    statement_id = Column(GUID(), ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)
    status = Column(ExistingEnum(ReconciliationRunStatus, name="bank_reconciliation_status"), nullable=False)
    config = Column(JSON_TYPE, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankReconciliationMatch(Base):
    __tablename__ = "bank_reconciliation_matches"
    __table_args__ = (
        Index("ix_bank_reconciliation_matches_run", "run_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    run_id = Column(GUID(), ForeignKey("bank_reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    bank_tx_id = Column(GUID(), ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(String(36), nullable=True)
    match_type = Column(ExistingEnum(ReconciliationMatchType, name="bank_reconciliation_match_type"), nullable=False)
    score = Column(Numeric(5, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BankReconciliationDiff(Base):
    __tablename__ = "bank_reconciliation_diffs"
    __table_args__ = (
        Index("ix_bank_reconciliation_diffs_run", "run_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    run_id = Column(GUID(), ForeignKey("bank_reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    source = Column(ExistingEnum(ReconciliationDiffSource, name="bank_reconciliation_diff_source"), nullable=False)
    tx_id = Column(String(64), nullable=False)
    reason = Column(ExistingEnum(ReconciliationDiffReason, name="bank_reconciliation_diff_reason"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "BankReconciliationDiff",
    "BankReconciliationMatch",
    "BankReconciliationRun",
    "BankStatement",
    "BankStatementStatus",
    "BankTransaction",
    "BankTransactionDirection",
    "IntegrationExport",
    "IntegrationExportStatus",
    "IntegrationFile",
    "IntegrationMapping",
    "IntegrationType",
    "ReconciliationDiffReason",
    "ReconciliationDiffSource",
    "ReconciliationMatchType",
    "ReconciliationRunStatus",
]

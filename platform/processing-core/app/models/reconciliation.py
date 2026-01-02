from __future__ import annotations

from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects import postgresql

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ReconciliationScope(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class ReconciliationRunStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationDiscrepancyType(str, Enum):
    BALANCE_MISMATCH = "balance_mismatch"
    MISSING_ENTRY = "missing_entry"
    DUPLICATE_ENTRY = "duplicate_entry"
    UNMATCHED_EXTERNAL = "unmatched_external"
    UNMATCHED_INTERNAL = "unmatched_internal"
    FX_NOT_SUPPORTED = "fx_not_supported"
    MISMATCHED_AMOUNT = "mismatched_amount"


class ReconciliationDiscrepancyStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        Index("ix_reconciliation_runs_scope_created", "scope", "created_at"),
        Index("ix_reconciliation_runs_provider_created", "provider", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    scope = Column(ExistingEnum(ReconciliationScope, name="reconciliation_run_scope"), nullable=False)
    provider = Column(String(64), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        ExistingEnum(ReconciliationRunStatus, name="reconciliation_run_status"),
        nullable=False,
        default=ReconciliationRunStatus.STARTED,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id = Column(GUID(), nullable=True)
    summary = Column(JSON_TYPE, nullable=True)
    audit_event_id = Column(GUID(), nullable=True)


class ReconciliationDiscrepancy(Base):
    __tablename__ = "reconciliation_discrepancies"
    __table_args__ = (
        Index("ix_reconciliation_discrepancies_run_status", "run_id", "status"),
        Index("ix_reconciliation_discrepancies_account_created", "ledger_account_id", "created_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    run_id = Column(GUID(), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    ledger_account_id = Column(GUID(), ForeignKey("internal_ledger_accounts.id"), nullable=True)
    currency = Column(String(8), nullable=False)
    discrepancy_type = Column(
        ExistingEnum(ReconciliationDiscrepancyType, name="reconciliation_discrepancy_type"),
        nullable=False,
    )
    internal_amount = Column(sa.Numeric(18, 4), nullable=True)
    external_amount = Column(sa.Numeric(18, 4), nullable=True)
    delta = Column(sa.Numeric(18, 4), nullable=True)
    details = Column(JSON_TYPE, nullable=True)
    status = Column(
        ExistingEnum(ReconciliationDiscrepancyStatus, name="reconciliation_discrepancy_status"),
        nullable=False,
        default=ReconciliationDiscrepancyStatus.OPEN,
    )
    resolution = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExternalStatement(Base):
    __tablename__ = "external_statements"
    __table_args__ = (
        Index("ix_external_statements_provider_period", "provider", "period_end"),
        sa.UniqueConstraint("provider", "source_hash", name="uq_external_statements_source"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    provider = Column(String(64), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    currency = Column(String(8), nullable=False)
    total_in = Column(sa.Numeric(18, 4), nullable=True)
    total_out = Column(sa.Numeric(18, 4), nullable=True)
    closing_balance = Column(sa.Numeric(18, 4), nullable=True)
    lines = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_hash = Column(String(64), nullable=False)
    audit_event_id = Column(GUID(), nullable=True)


class ReconciliationLinkDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class ReconciliationLinkStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    MISMATCHED = "mismatched"


class ReconciliationLink(Base):
    __tablename__ = "reconciliation_links"
    __table_args__ = (
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_reconciliation_link_entity"),
        Index("ix_reconciliation_links_provider_status_expected", "provider", "status", "expected_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(GUID(), nullable=False)
    provider = Column(String(64), nullable=False)
    currency = Column(String(8), nullable=False)
    expected_amount = Column(sa.Numeric(18, 4), nullable=False)
    direction = Column(ExistingEnum(ReconciliationLinkDirection, name="reconciliation_link_direction"), nullable=False)
    expected_at = Column(DateTime(timezone=True), nullable=False)
    match_key = Column(String(128), nullable=True)
    status = Column(ExistingEnum(ReconciliationLinkStatus, name="reconciliation_link_status"), nullable=False)
    run_id = Column(GUID(), ForeignKey("reconciliation_runs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "ExternalStatement",
    "ReconciliationDiscrepancy",
    "ReconciliationDiscrepancyStatus",
    "ReconciliationDiscrepancyType",
    "ReconciliationLink",
    "ReconciliationLinkDirection",
    "ReconciliationLinkStatus",
    "ReconciliationRun",
    "ReconciliationRunStatus",
    "ReconciliationScope",
]

from __future__ import annotations

from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID


class BillingReconciliationStatus(str, Enum):
    OK = "OK"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class BillingReconciliationVerdict(str, Enum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    MISSING_LEDGER = "MISSING_LEDGER"
    ERROR = "ERROR"


class BillingReconciliationRun(Base):
    __tablename__ = "billing_reconciliation_runs"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False, index=True)
    status = Column(
        SAEnum(BillingReconciliationStatus, name="billing_reconciliation_status"),
        nullable=False,
        default=BillingReconciliationStatus.OK,
    )
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total_invoices = Column(Integer, nullable=False, default=0)
    ok_count = Column(Integer, nullable=False, default=0)
    mismatch_count = Column(Integer, nullable=False, default=0)
    missing_ledger_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BillingReconciliationItem(Base):
    __tablename__ = "billing_reconciliation_items"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    run_id = Column(GUID(), ForeignKey("billing_reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(String(36), nullable=False)
    client_id = Column(String(64), nullable=False)
    currency = Column(String(3), nullable=False)
    verdict = Column(
        SAEnum(BillingReconciliationVerdict, name="billing_reconciliation_verdict"),
        nullable=False,
        default=BillingReconciliationVerdict.OK,
    )
    diff_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "BillingReconciliationItem",
    "BillingReconciliationRun",
    "BillingReconciliationStatus",
    "BillingReconciliationVerdict",
]

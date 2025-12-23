from __future__ import annotations

from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID


class BillingJobType(str, Enum):
    BILLING_DAILY = "BILLING_DAILY"
    BILLING_FINALIZE = "BILLING_FINALIZE"
    INVOICE_MONTHLY = "INVOICE_MONTHLY"
    RECONCILIATION = "RECONCILIATION"
    MANUAL_RUN = "MANUAL_RUN"
    PDF_GENERATE = "PDF_GENERATE"
    INVOICE_SEND = "INVOICE_SEND"
    CREDIT_NOTE_PDF = "CREDIT_NOTE_PDF"
    FINANCE_EXPORT = "FINANCE_EXPORT"
    BALANCE_REBUILD = "BALANCE_REBUILD"
    CLEARING = "CLEARING"


class BillingJobStatus(str, Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BillingJobRun(Base):
    __tablename__ = "billing_job_runs"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    job_type = Column(ExistingEnum(BillingJobType, name="billing_job_type"), nullable=False)
    params = Column(JSON, nullable=True)
    status = Column(ExistingEnum(BillingJobStatus, name="billing_job_status"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)
    duration_ms = Column(sa.Integer, nullable=True)
    celery_task_id = Column(String(128), nullable=True, index=True)
    correlation_id = Column(String(128), nullable=True, index=True)
    invoice_id = Column(String(36), nullable=True, index=True)
    billing_period_id = Column(GUID(), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    attempts = Column(sa.Integer, nullable=True, default=0)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    result_ref = Column(JSON, nullable=True)


__all__ = ["BillingJobRun", "BillingJobStatus", "BillingJobType"]

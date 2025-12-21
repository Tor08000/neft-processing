from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, Text, func
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import GUID


class BillingJobType(str, Enum):
    BILLING_DAILY = "BILLING_DAILY"
    BILLING_FINALIZE = "BILLING_FINALIZE"
    INVOICE_MONTHLY = "INVOICE_MONTHLY"
    RECONCILIATION = "RECONCILIATION"
    MANUAL_RUN = "MANUAL_RUN"


class BillingJobStatus(str, Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BillingJobRun(Base):
    __tablename__ = "billing_job_runs"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    job_type = Column(SAEnum(BillingJobType, name="billing_job_type"), nullable=False)
    params = Column(JSON, nullable=True)
    status = Column(SAEnum(BillingJobStatus, name="billing_job_status"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)


__all__ = ["BillingJobRun", "BillingJobStatus", "BillingJobType"]

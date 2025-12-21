from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, Text, func

from app.db import Base
from app.db.types import GUID


class BillingTaskType(str, Enum):
    MONTHLY_RUN = "MONTHLY_RUN"
    PDF_GENERATE = "PDF_GENERATE"
    INVOICE_SEND = "INVOICE_SEND"


class BillingTaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BillingTaskLink(Base):
    """Tracks Celery tasks associated with invoices for idempotency and audit."""

    __tablename__ = "billing_task_links"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid4()))
    invoice_id = Column(String(36), nullable=False, index=True)
    task_type = Column(SAEnum(BillingTaskType, name="billing_task_type"), nullable=False)
    task_id = Column(String, nullable=False)
    status = Column(SAEnum(BillingTaskStatus, name="billing_task_status"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


__all__ = ["BillingTaskLink", "BillingTaskStatus", "BillingTaskType"]

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, UniqueConstraint, func

from app.db import Base


class BillingPeriodType(str, Enum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"


class BillingPeriodStatus(str, Enum):
    OPEN = "OPEN"
    FINALIZED = "FINALIZED"
    LOCKED = "LOCKED"


class BillingPeriod(Base):
    __tablename__ = "billing_periods"
    __table_args__ = (
        UniqueConstraint(
            "period_type",
            "start_at",
            "end_at",
            name="uq_billing_period_scope",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    period_type = Column(SAEnum(BillingPeriodType, name="billing_period_type"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    tz = Column(String(64), nullable=False)
    status = Column(
        SAEnum(BillingPeriodStatus, name="billing_period_status"),
        nullable=False,
        default=BillingPeriodStatus.OPEN,
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["BillingPeriod", "BillingPeriodStatus", "BillingPeriodType"]

from __future__ import annotations

from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Enum as SAEnum, UniqueConstraint, func

from app.db import Base
from app.db.types import GUID, new_uuid_str


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
        sa.Index("ix_billing_periods_type_start", "period_type", "start_at"),
        sa.Index("ix_billing_periods_status", "status"),
        sa.Index("ix_billing_periods_start_at", "start_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    period_type = Column(SAEnum(BillingPeriodType, name="billing_period_type"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    tz = Column(sa.String(64), nullable=False)
    status = Column(
        SAEnum(BillingPeriodStatus, name="billing_period_status"),
        nullable=False,
        default=BillingPeriodStatus.OPEN,
        server_default=sa.text("'OPEN'"),
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

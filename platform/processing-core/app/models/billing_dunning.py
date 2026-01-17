from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.types import BigInteger

from app.db import Base
from app.db.types import ExistingEnum


class BillingDunningEventType(str, Enum):
    DUE_SOON_7D = "DUE_SOON_7D"
    DUE_SOON_1D = "DUE_SOON_1D"
    OVERDUE_1D = "OVERDUE_1D"
    OVERDUE_7D = "OVERDUE_7D"
    PRE_SUSPEND_1D = "PRE_SUSPEND_1D"
    SUSPENDED = "SUSPENDED"


class BillingDunningChannel(str, Enum):
    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class BillingDunningStatus(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class BillingDunningEvent(Base):
    __tablename__ = "billing_dunning_events"
    __table_args__ = (
        Index("ix_billing_dunning_events_org", "org_id", "sent_at"),
        Index("ix_billing_dunning_events_invoice", "invoice_id"),
        Index("ix_billing_dunning_events_channel", "channel", "status"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(BigInteger, nullable=False, index=True)
    invoice_id = Column(BigInteger, nullable=False, index=True)
    event_type = Column(
        ExistingEnum(BillingDunningEventType, name="billing_dunning_event_type"),
        nullable=False,
    )
    channel = Column(ExistingEnum(BillingDunningChannel, name="billing_dunning_channel"), nullable=False)
    status = Column(ExistingEnum(BillingDunningStatus, name="billing_dunning_status"), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(256), nullable=False, unique=True)
    error = Column(Text, nullable=True)


__all__ = [
    "BillingDunningChannel",
    "BillingDunningEvent",
    "BillingDunningEventType",
    "BillingDunningStatus",
]

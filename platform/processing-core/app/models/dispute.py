from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db import Base


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class DisputeEventType(str, Enum):
    OPENED = "OPENED"
    MOVED_TO_REVIEW = "MOVED_TO_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    HOLD_PLACED = "HOLD_PLACED"
    HOLD_RELEASED = "HOLD_RELEASED"
    REFUND_POSTED = "REFUND_POSTED"
    FEE_POSTED = "FEE_POSTED"


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    operation_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_business_id = Column(String(64), nullable=False, index=True)
    disputed_amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    fee_amount = Column(BigInteger, nullable=False, default=0)
    status = Column(
        SAEnum(DisputeStatus, name="dispute_status"),
        nullable=False,
        default=DisputeStatus.OPEN,
        index=True,
    )
    hold_placed = Column(Boolean, nullable=False, default=False)
    hold_posting_id = Column(PGUUID(as_uuid=True), nullable=True)
    resolution_posting_id = Column(PGUUID(as_uuid=True), nullable=True)
    initiator = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DisputeEvent(Base):
    __tablename__ = "dispute_events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    dispute_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(SAEnum(DisputeEventType, name="dispute_event_type"), nullable=False)
    payload = Column(JSON, nullable=True)
    actor = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


__all__ = ["Dispute", "DisputeEvent", "DisputeStatus", "DisputeEventType"]

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db import Base
from app.models.refund_request import SettlementPolicy


class ReversalStatus(str, Enum):
    REQUESTED = "REQUESTED"
    POSTED = "POSTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Reversal(Base):
    __tablename__ = "reversals"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    operation_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_business_id = Column(String(64), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    initiator = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    status = Column(
        SAEnum(ReversalStatus, name="reversal_status"),
        nullable=False,
        default=ReversalStatus.REQUESTED,
        index=True,
    )
    posted_posting_id = Column(PGUUID(as_uuid=True), nullable=True)
    settlement_policy = Column(
        SAEnum(SettlementPolicy, name="settlement_policy"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["Reversal", "ReversalStatus"]

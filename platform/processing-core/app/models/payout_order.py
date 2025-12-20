from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, Column, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class PayoutOrderStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PayoutOrder(Base):
    __tablename__ = "payout_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    settlement_id = Column(String(36), ForeignKey("settlements.id"), nullable=False, index=True)
    partner_bank_details_ref = Column(String(255), nullable=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(
        SAEnum(PayoutOrderStatus, name="payout_order_status"),
        nullable=False,
        server_default=PayoutOrderStatus.QUEUED.value,
        index=True,
    )
    provider_ref = Column(String(128), nullable=True, index=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    settlement = relationship("Settlement", back_populates="payout_order")
    events = relationship("PayoutEvent", back_populates="payout_order", cascade="all, delete-orphan")


__all__ = ["PayoutOrder", "PayoutOrderStatus"]

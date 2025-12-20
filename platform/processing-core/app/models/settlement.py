from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import BigInteger, Column, Date, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class SettlementStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint(
            "merchant_id", "currency", "period_from", "period_to", name="uq_settlement_scope"
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id = Column(String(64), nullable=False, index=True)
    partner_id = Column(String(64), nullable=True, index=True)
    period_from = Column(Date, nullable=False, index=True)
    period_to = Column(Date, nullable=False, index=True)
    currency = Column(String(8), nullable=False, index=True)
    total_amount = Column(BigInteger, nullable=False)
    commission_amount = Column(BigInteger, nullable=False, default=0)
    status = Column(
        SAEnum(SettlementStatus, name="settlement_status"),
        nullable=False,
        server_default=SettlementStatus.DRAFT.value,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    payout_order = relationship("PayoutOrder", back_populates="settlement", uselist=False)


__all__ = ["Settlement", "SettlementStatus"]

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import BigInteger, Column, Date, DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.db import Base


class FinancialAdjustmentKind(str, Enum):
    REFUND_ADJUSTMENT = "REFUND_ADJUSTMENT"
    REVERSAL_ADJUSTMENT = "REVERSAL_ADJUSTMENT"
    DISPUTE_ADJUSTMENT = "DISPUTE_ADJUSTMENT"
    FEE_ADJUSTMENT = "FEE_ADJUSTMENT"


class RelatedEntityType(str, Enum):
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    DISPUTE = "DISPUTE"


class FinancialAdjustmentStatus(str, Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    FAILED = "FAILED"


class FinancialAdjustment(Base):
    __tablename__ = "financial_adjustments"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    kind = Column(SAEnum(FinancialAdjustmentKind, name="financial_adjustment_kind"), nullable=False)
    related_entity_type = Column(SAEnum(RelatedEntityType, name="financial_adjustment_related"), nullable=False)
    related_entity_id = Column(PGUUID(as_uuid=True), nullable=False)
    operation_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(
        SAEnum(FinancialAdjustmentStatus, name="financial_adjustment_status"),
        nullable=False,
        default=FinancialAdjustmentStatus.PENDING,
        index=True,
    )
    posting_id = Column(PGUUID(as_uuid=True), nullable=True)
    effective_date = Column(Date, nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = [
    "FinancialAdjustment",
    "FinancialAdjustmentKind",
    "FinancialAdjustmentStatus",
    "RelatedEntityType",
]

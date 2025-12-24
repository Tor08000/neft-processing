from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db import Base


json_variant = JSON().with_variant(postgresql.JSONB, "postgresql")


class PayoutBatchState(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class PayoutBatch(Base):
    __tablename__ = "payout_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, nullable=False, index=True)
    partner_id = Column(String(64), nullable=False, index=True)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    state = Column(
        SAEnum(PayoutBatchState, name="payout_batch_state"),
        nullable=False,
        server_default=PayoutBatchState.DRAFT.value,
        index=True,
    )
    total_amount = Column(Numeric(18, 2), nullable=False, server_default="0")
    total_qty = Column(Numeric(18, 3), nullable=False, server_default="0")
    operations_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    provider = Column(String(64), nullable=True)
    external_ref = Column(String(128), nullable=True)
    meta = Column(json_variant, nullable=True)

    items = relationship("PayoutItem", back_populates="batch", cascade="all, delete-orphan")


class PayoutItem(Base):
    __tablename__ = "payout_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id = Column(String(36), ForeignKey("payout_batches.id"), nullable=False, index=True)
    azs_id = Column(String(64), nullable=True)
    product_id = Column(String(64), nullable=True)
    amount_gross = Column(Numeric(18, 2), nullable=False)
    commission_amount = Column(Numeric(18, 2), nullable=False, server_default="0")
    amount_net = Column(Numeric(18, 2), nullable=False)
    qty = Column(Numeric(18, 3), nullable=False, server_default="0")
    operations_count = Column(Integer, nullable=False, server_default="0")
    meta = Column(json_variant, nullable=True)

    batch = relationship("PayoutBatch", back_populates="items")


__all__ = ["PayoutBatch", "PayoutBatchState", "PayoutItem"]

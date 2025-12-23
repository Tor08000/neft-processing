from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Enum, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base


class ClearingBatch(Base):
    __tablename__ = "clearing_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date_from", "date_to", name="uq_clearing_batch_tenant_period"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id = Column(String(64), nullable=False, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    date_from = Column(Date, nullable=False, index=True)
    date_to = Column(Date, nullable=False, index=True)
    total_amount = Column(Integer, nullable=False)
    total_qty = Column(Numeric(18, 3), nullable=True)
    operations_count = Column(Integer, nullable=False, default=0)
    state = Column(
        Enum("OPEN", "CLOSED", name="clearing_batch_state"),
        nullable=False,
        server_default="OPEN",
        index=True,
    )
    status = Column(
        Enum("PENDING", "SENT", "CONFIRMED", "FAILED", name="clearing_batch_status"),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

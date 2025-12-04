from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Enum as SAEnum, JSON, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger

from app.db import Base


class Clearing(Base):
    __tablename__ = "clearing"
    __table_args__ = (
        UniqueConstraint(
            "batch_date", "merchant_id", "currency", name="uq_clearing_date_merchant_currency"
        ),
        {
            "sqlite_autoincrement": True,
        },
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_date = Column(Date, nullable=False, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    currency = Column(String(3), nullable=False, index=True)
    total_amount = Column(BigInteger, nullable=False)
    status = Column(
        SAEnum("PENDING", name="clearing_status"),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

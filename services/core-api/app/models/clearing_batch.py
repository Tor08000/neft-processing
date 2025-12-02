from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from app.db import Base


class ClearingBatch(Base):
    __tablename__ = "clearing_batch"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id = Column(String(64), nullable=False, index=True)
    date_from = Column(Date, nullable=False, index=True)
    date_to = Column(Date, nullable=False, index=True)
    total_amount = Column(Integer, nullable=False)
    operations_count = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum("PENDING", "SENT", "CONFIRMED", "FAILED", name="clearing_batch_status"),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

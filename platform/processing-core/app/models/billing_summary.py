from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


class BillingSummary(Base):
    __tablename__ = "billing_summary"
    __table_args__ = (
        UniqueConstraint("date", "merchant_id", name="uq_billing_summary_date_merchant"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    date = Column(Date, nullable=False, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    total_captured_amount = Column(Integer, nullable=False, default=0)
    operations_count = Column(Integer, nullable=False, default=0)

    status = Column(
        Enum("PENDING", "FINALIZED", name="billing_summary_status"),
        nullable=False,
        server_default="PENDING",
        index=True,
    )
    generated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    hash = Column(String(128), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

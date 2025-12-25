from uuid import uuid4

from enum import Enum
from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, Index, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import synonym

from app.db import Base
from app.models.operation import ProductType
from app.db.types import GUID


class BillingSummaryStatus(str, Enum):
    PENDING = "PENDING"
    FINALIZED = "FINALIZED"


class BillingSummary(Base):
    __tablename__ = "billing_summary"
    __table_args__ = (
        UniqueConstraint(
            "billing_date",
            "merchant_id",
            "client_id",
            "product_type",
            "currency",
            name="uq_billing_summary_unique_scope",
        ),
        Index("ix_billing_summary_status_billing_date", "status", "billing_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    billing_date = Column(Date, nullable=False, index=True)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    product_type = Column(SAEnum(ProductType), nullable=True, index=True)
    currency = Column(String(3), nullable=True, index=True)

    total_amount = Column(BigInteger, nullable=False, default=0)
    total_quantity = Column(Numeric(18, 3), nullable=True)
    operations_count = Column(Integer, nullable=False, default=0)
    commission_amount = Column(BigInteger, nullable=False, default=0)
    status = Column(
        SAEnum(BillingSummaryStatus),
        nullable=False,
        server_default=BillingSummaryStatus.PENDING.value,
        default=BillingSummaryStatus.PENDING,
        index=True,
    )
    generated_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    hash = Column(String(128), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Aliases for backwards compatibility
    date = synonym("billing_date")
    total_captured_amount = synonym("total_amount")

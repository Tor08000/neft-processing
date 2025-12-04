from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base
from app.models.operation import ProductType


class BillingSummary(Base):
    __tablename__ = "billing_summary"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "client_id",
            "merchant_id",
            "product_type",
            "currency",
            name="uq_billing_summary_date_group",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    date = Column(Date, nullable=False, index=True)
    client_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    product_type = Column(Enum(ProductType), nullable=True, index=True)
    currency = Column(String(3), nullable=False, index=True, default="RUB")

    total_amount = Column(BigInteger, nullable=False, default=0)
    total_quantity = Column(Numeric(18, 3), nullable=True)
    operations_count = Column(Integer, nullable=False, default=0)
    commission_amount = Column(BigInteger, nullable=False, default=0)

    # Legacy fields kept for compatibility with existing clearing logic
    total_captured_amount = Column(Integer, nullable=False, default=0)

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

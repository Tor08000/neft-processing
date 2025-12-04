from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger, Numeric
from sqlalchemy import Enum as SAEnum

from app.db import Base
from app.models.operation import ProductType


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
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    billing_date = Column(Date, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    product_type = Column(SAEnum(ProductType), nullable=True, index=True)
    currency = Column(String(3), nullable=False, index=True)

    total_amount = Column(BigInteger, nullable=False, default=0)
    total_quantity = Column(Numeric(18, 3), nullable=True)
    operations_count = Column(Integer, nullable=False, default=0)
    commission_amount = Column(BigInteger, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

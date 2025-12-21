from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import BigInteger

from app.db import Base
from app.db.types import GUID


class InvoiceStatus(str, Enum):
    """Lifecycle of invoices issued to clients."""

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SENT = "SENT"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class InvoicePdfStatus(str, Enum):
    """Lifecycle of invoice PDF artifact."""

    NONE = "NONE"
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"


class Invoice(Base):
    """Client invoice aggregated for a billing period."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "billing_period_id",
            "currency",
            name="uq_invoice_scope",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    client_id = Column(String(64), nullable=False, index=True)
    period_from = Column(Date, nullable=False, index=True)
    period_to = Column(Date, nullable=False, index=True)
    currency = Column(String(3), nullable=False)
    billing_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=True, index=True)

    total_amount = Column(BigInteger, nullable=False, default=0)
    tax_amount = Column(BigInteger, nullable=False, default=0)
    total_with_tax = Column(BigInteger, nullable=False, default=0)

    status = Column(SAEnum(InvoiceStatus), nullable=False, index=True, default=InvoiceStatus.DRAFT)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    external_number = Column(String(64), nullable=True)
    pdf_url = Column(String(512), nullable=True)
    pdf_status = Column(SAEnum(InvoicePdfStatus), nullable=False, server_default=InvoicePdfStatus.NONE.value)
    pdf_generated_at = Column(DateTime(timezone=True), nullable=True)
    pdf_hash = Column(String(128), nullable=True)
    pdf_version = Column(Integer, nullable=True)
    pdf_error = Column(String(2048), nullable=True)

    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLine(Base):
    """Line item describing a single billed product or operation."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id",
            "operation_id",
            name="uq_invoice_line_operation_per_invoice",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)

    operation_id = Column(String(128), nullable=False)
    card_id = Column(String(64), nullable=True)
    product_id = Column(String(64), nullable=False)

    liters = Column(Numeric(18, 3), nullable=True)
    unit_price = Column(Numeric(18, 3), nullable=True)

    line_amount = Column(BigInteger, nullable=False)
    tax_amount = Column(BigInteger, nullable=False, default=0)

    partner_id = Column(String(64), nullable=True)
    azs_id = Column(String(64), nullable=True)

    invoice = relationship("Invoice", back_populates="lines")

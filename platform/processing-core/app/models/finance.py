from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID


class PaymentStatus(str, Enum):
    POSTED = "POSTED"
    FAILED = "FAILED"


class CreditNoteStatus(str, Enum):
    POSTED = "POSTED"
    FAILED = "FAILED"


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_ref",
            name="uq_invoice_payments_provider_external_ref",
        ),
    )

    id = Column(GUID(), primary_key=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    provider = Column(String(64), nullable=True)
    external_ref = Column(String(128), nullable=True, index=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(
        ExistingEnum(PaymentStatus, name="invoice_payment_status"),
        nullable=False,
        default=PaymentStatus.POSTED,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id = Column(GUID(), primary_key=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    reason = Column(String(255), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(
        ExistingEnum(CreditNoteStatus, name="credit_note_status"),
        nullable=False,
        default=CreditNoteStatus.POSTED,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


__all__ = [
    "InvoicePayment",
    "CreditNote",
    "PaymentStatus",
    "CreditNoteStatus",
]

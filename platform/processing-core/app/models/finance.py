from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class PaymentStatus(str, Enum):
    POSTED = "POSTED"
    FAILED = "FAILED"


class CreditNoteStatus(str, Enum):
    POSTED = "POSTED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class SettlementSourceType(str, Enum):
    PAYMENT = "PAYMENT"
    CREDIT_NOTE = "CREDIT_NOTE"
    REFUND = "REFUND"


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    provider = Column(String(64), nullable=True)
    external_ref = Column(String(128), nullable=True, index=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    response_hash = Column(String(64), nullable=False, server_default="")
    status = Column(
        ExistingEnum(PaymentStatus, name="invoice_payment_status"),
        nullable=False,
        default=PaymentStatus.POSTED,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_invoice_payments_provider_external_ref",
            func.coalesce(provider, ""),
            external_ref,
            unique=True,
        ),
    )


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    provider = Column(String(64), nullable=True)
    external_ref = Column(String(128), nullable=True, index=True)
    reason = Column(String(255), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    response_hash = Column(String(64), nullable=False, server_default="")
    status = Column(
        ExistingEnum(CreditNoteStatus, name="credit_note_status"),
        nullable=False,
        default=CreditNoteStatus.POSTED,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InvoiceSettlementAllocation(Base):
    __tablename__ = "invoice_settlement_allocations"
    __table_args__ = (
        UniqueConstraint("invoice_id", "source_type", "source_id", name="uq_settlement_alloc_scope"),
        Index("ix_alloc_invoice_id", "invoice_id"),
        Index("ix_alloc_settlement_period_id", "settlement_period_id"),
        Index("ix_alloc_client_period", "client_id", "settlement_period_id"),
        Index("ix_alloc_source", "source_type", "source_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=False)
    settlement_period_id = Column(GUID(), ForeignKey("billing_periods.id"), nullable=False)
    source_type = Column(ExistingEnum(SettlementSourceType, name="settlement_source_type"), nullable=False)
    source_id = Column(String(36), nullable=False)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


__all__ = [
    "InvoicePayment",
    "CreditNote",
    "PaymentStatus",
    "CreditNoteStatus",
    "InvoiceSettlementAllocation",
    "SettlementSourceType",
]

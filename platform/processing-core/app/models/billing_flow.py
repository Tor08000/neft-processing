from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class BillingInvoiceStatus(str, Enum):
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    VOID = "VOID"


class BillingPaymentStatus(str, Enum):
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED_PARTIAL = "REFUNDED_PARTIAL"
    REFUNDED_FULL = "REFUNDED_FULL"


class BillingRefundStatus(str, Enum):
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_billing_invoices_number"),
        UniqueConstraint("idempotency_key", name="uq_billing_invoices_idempotency"),
        Index("ix_billing_invoices_client_status", "client_id", "status"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invoice_number = Column(String(64), nullable=False)
    client_id = Column(GUID(), nullable=False, index=True)
    case_id = Column(GUID(), nullable=True, index=True)
    currency = Column(String(8), nullable=False)
    amount_total = Column(Numeric(18, 4), nullable=False)
    amount_paid = Column(Numeric(18, 4), nullable=False, server_default="0")
    status = Column(ExistingEnum(BillingInvoiceStatus, name="billing_invoice_status"), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    ledger_tx_id = Column(GUID(), nullable=False)
    audit_event_id = Column(GUID(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BillingPayment(Base):
    __tablename__ = "billing_payments"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_billing_payments_idempotency"),
        Index("ix_billing_payments_invoice", "invoice_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    invoice_id = Column(GUID(), ForeignKey("billing_invoices.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(64), nullable=False)
    provider_payment_id = Column(String(128), nullable=True)
    currency = Column(String(8), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(BillingPaymentStatus, name="billing_payment_status"), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    ledger_tx_id = Column(GUID(), nullable=False)
    external_statement_line_id = Column(String(128), nullable=True)
    audit_event_id = Column(GUID(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BillingRefund(Base):
    __tablename__ = "billing_refunds"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_billing_refunds_idempotency"),
        Index("ix_billing_refunds_payment", "payment_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    payment_id = Column(GUID(), ForeignKey("billing_payments.id", ondelete="CASCADE"), nullable=False)
    provider_refund_id = Column(String(128), nullable=True)
    currency = Column(String(8), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    refunded_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(ExistingEnum(BillingRefundStatus, name="billing_refund_status"), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    ledger_tx_id = Column(GUID(), nullable=False)
    external_statement_line_id = Column(String(128), nullable=True)
    audit_event_id = Column(GUID(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = [
    "BillingInvoice",
    "BillingInvoiceStatus",
    "BillingPayment",
    "BillingPaymentStatus",
    "BillingRefund",
    "BillingRefundStatus",
]

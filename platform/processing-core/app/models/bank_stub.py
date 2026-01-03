from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class BankStubPaymentStatus(str, Enum):
    CREATED = "CREATED"
    POSTED = "POSTED"
    SETTLED = "SETTLED"
    REVERSED = "REVERSED"


class BankStubPayment(Base):
    __tablename__ = "bank_stub_payments"
    __table_args__ = (
        UniqueConstraint("payment_ref", name="uq_bank_stub_payments_ref"),
        UniqueConstraint("idempotency_key", name="uq_bank_stub_payments_idempotency"),
        Index("ix_bank_stub_payments_invoice", "invoice_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    invoice_id = Column(GUID(), nullable=False)
    payment_ref = Column(String(128), nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    status = Column(ExistingEnum(BankStubPaymentStatus, name="bank_stub_payment_status"), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BankStubStatement(Base):
    __tablename__ = "bank_stub_statements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "checksum", name="uq_bank_stub_statements_checksum"),
        Index("ix_bank_stub_statements_period", "tenant_id", "period_to"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    period_from = Column(DateTime(timezone=True), nullable=False)
    period_to = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON_TYPE, nullable=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lines = relationship(
        "BankStubStatementLine",
        back_populates="statement",
        cascade="all, delete-orphan",
    )


class BankStubStatementLine(Base):
    __tablename__ = "bank_stub_statement_lines"
    __table_args__ = (
        Index("ix_bank_stub_statement_lines_statement", "statement_id"),
        UniqueConstraint("statement_id", "payment_ref", name="uq_bank_stub_statement_lines_ref"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    statement_id = Column(GUID(), ForeignKey("bank_stub_statements.id", ondelete="CASCADE"), nullable=False)
    payment_ref = Column(String(128), nullable=False)
    invoice_number = Column(String(64), nullable=True)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(8), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    statement = relationship("BankStubStatement", back_populates="lines")


__all__ = [
    "BankStubPayment",
    "BankStubPaymentStatus",
    "BankStubStatement",
    "BankStubStatementLine",
]

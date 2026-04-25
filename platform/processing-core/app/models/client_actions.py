from __future__ import annotations

from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ReconciliationRequestStatus(str, Enum):
    REQUESTED = "REQUESTED"
    IN_PROGRESS = "IN_PROGRESS"
    GENERATED = "GENERATED"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ReconciliationRequest(Base):
    __tablename__ = "reconciliation_requests"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    date_from = Column(Date, nullable=False, index=True)
    date_to = Column(Date, nullable=False, index=True)
    status = Column(
        ExistingEnum(ReconciliationRequestStatus, name="reconciliation_request_status"),
        nullable=False,
        default=ReconciliationRequestStatus.REQUESTED,
        index=True,
    )
    requested_by_user_id = Column(Text, nullable=True)
    requested_by_email = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    result_object_key = Column(Text, nullable=True)
    result_bucket = Column(Text, nullable=True)
    result_hash_sha256 = Column(String(64), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    note_client = Column(Text, nullable=True)
    note_ops = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("date_from <= date_to", name="ck_reconciliation_requests_period"),)


class DocumentAcknowledgement(Base):
    __tablename__ = "document_acknowledgements"
    __table_args__ = (
        UniqueConstraint("client_id", "document_type", "document_id", name="uq_document_acknowledgements_scope"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    document_type = Column(String(64), nullable=False)
    document_id = Column(String(64), nullable=False)
    document_object_key = Column(Text, nullable=True)
    document_hash = Column(String(64), nullable=True)
    ack_by_user_id = Column(Text, nullable=True)
    ack_by_email = Column(Text, nullable=True)
    ack_ip = Column(Text, nullable=True)
    ack_user_agent = Column(Text, nullable=True)
    ack_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ack_method = Column(String(32), nullable=True)


class InvoiceThreadStatus(str, Enum):
    OPEN = "OPEN"
    WAITING_SUPPORT = "WAITING_SUPPORT"
    WAITING_CLIENT = "WAITING_CLIENT"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class InvoiceMessageSenderType(str, Enum):
    CLIENT = "CLIENT"
    SUPPORT = "SUPPORT"
    SYSTEM = "SYSTEM"


class InvoiceThread(Base):
    __tablename__ = "invoice_threads"
    __table_args__ = (UniqueConstraint("invoice_id", name="uq_invoice_thread_invoice"),)

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    client_id = Column(String(64), nullable=False, index=True)
    status = Column(
        ExistingEnum(InvoiceThreadStatus, name="invoice_thread_status"),
        nullable=False,
        default=InvoiceThreadStatus.OPEN,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)

    messages = relationship("InvoiceMessage", back_populates="thread", cascade="all, delete-orphan")


class InvoiceMessage(Base):
    __tablename__ = "invoice_messages"

    id = Column(String(36), primary_key=True, default=new_uuid_str)
    thread_id = Column(String(36), ForeignKey("invoice_threads.id"), nullable=False, index=True)
    sender_type = Column(
        ExistingEnum(InvoiceMessageSenderType, name="invoice_message_sender_type"),
        nullable=False,
        index=True,
    )
    sender_user_id = Column(Text, nullable=True)
    sender_email = Column(Text, nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    thread = relationship("InvoiceThread", back_populates="messages")


__all__ = [
    "ReconciliationRequest",
    "ReconciliationRequestStatus",
    "DocumentAcknowledgement",
    "InvoiceThread",
    "InvoiceThreadStatus",
    "InvoiceMessage",
    "InvoiceMessageSenderType",
]

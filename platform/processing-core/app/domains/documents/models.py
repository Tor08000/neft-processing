from __future__ import annotations

import enum

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.db.types import GUID


class DocumentDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class DocumentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY_TO_SEND = "READY_TO_SEND"
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    SIGNED = "SIGNED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    DELIVERED = "DELIVERED"
    READY_TO_SIGN = "READY_TO_SIGN"
    SIGNED_CLIENT = "SIGNED_CLIENT"
    CLOSED = "CLOSED"


class DocumentSenderType(str, enum.Enum):
    NEFT = "NEFT"
    CLIENT = "CLIENT"
    PARTNER = "PARTNER"


class EdoStatus(str, enum.Enum):
    NEW = "NEW"
    SENDING = "SENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED = "SIGNED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    EDO_NOT_CONFIGURED = "EDO_NOT_CONFIGURED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_client_direction_status", "client_id", "direction", "status"),
        Index("ix_documents_client_created_desc", "client_id", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False, default=DocumentSenderType.NEFT.value)
    sender_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_inn: Mapped[str | None] = mapped_column(Text, nullable=True)
    number: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Numeric | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    signed_by_client_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_by_client_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)

    files: Mapped[list["DocumentFile"]] = relationship(back_populates="document")
    edo_state: Mapped["DocumentEdoState | None"] = relationship(back_populates="document", uselist=False)
    signatures: Mapped[list["DocumentSignature"]] = relationship(back_populates="document")


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        Index("ix_document_files_document_id", "document_id"),
        UniqueConstraint("document_id", "storage_key", name="uq_document_files_document_storage_key"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="files")


class DocumentTimelineEvent(Base):
    __tablename__ = "document_timeline_events"
    __table_args__ = (
        Index("idx_doc_timeline_doc_id_created_at", "document_id", "created_at"),
        Index("idx_doc_timeline_client_id_created_at", "client_id", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentEdoState(Base):
    __tablename__ = "document_edostate"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_edostate_document_id"),
        Index("idx_document_edostate_next_poll_at", "next_poll_at"),
        Index("idx_document_edostate_client_id_status", "client_id", "edo_status"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="real")
    edo_status: Mapped[str] = mapped_column(String(32), nullable=False, default=EdoStatus.NEW.value)
    edo_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts_send: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    attempts_poll: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    next_poll_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_polled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="edo_state")


class DocumentSignature(Base):
    __tablename__ = "document_signatures"
    __table_args__ = (
        UniqueConstraint("document_id", "signer_user_id", "signature_method", name="uq_doc_signature_per_user_method"),
        Index("ix_document_signatures_client_id", "client_id"),
        Index("ix_document_signatures_document_id", "document_id"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    signer_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    signer_type: Mapped[str] = mapped_column(Text, nullable=False, default="CLIENT_USER")
    signature_method: Mapped[str] = mapped_column(String(16), nullable=False, default="SIMPLE")
    consent_text_version: Mapped[str] = mapped_column(Text, nullable=False)
    document_hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="signatures")

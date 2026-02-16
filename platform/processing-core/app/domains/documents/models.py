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
    doc_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
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

    files: Mapped[list["DocumentFile"]] = relationship(back_populates="document")


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

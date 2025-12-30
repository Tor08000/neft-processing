from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped

from app.db import Base


class EdoProvider(str, Enum):
    DIADOK = "DIADOK"
    SBIS = "SBIS"


class EdoDocumentStatus(str, Enum):
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED_BY_US = "SIGNED_BY_US"
    SIGNED_BY_COUNTERPARTY = "SIGNED_BY_COUNTERPARTY"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class EdoDocument(Base):
    __tablename__ = "edo_documents"
    __table_args__ = (
        UniqueConstraint("document_id", "provider", name="uq_edo_documents_document_provider"),
        Index("ix_edo_documents_status_retry", "status", "next_retry_at"),
    )

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    signature_id: Mapped[str | None] = Column(String(36), nullable=True)
    provider: Mapped[str] = Column(String(32), nullable=False, index=True)
    status: Mapped[str] = Column(String(32), nullable=False, index=True)

    provider_message_id: Mapped[str | None] = Column(String(128), nullable=True)
    provider_document_id: Mapped[str | None] = Column(String(128), nullable=True)

    attempt: Mapped[int] = Column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = Column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_status_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)

    meta: Mapped[dict | None] = Column(JSON, nullable=True)


__all__ = ["EdoDocument", "EdoDocumentStatus", "EdoProvider"]

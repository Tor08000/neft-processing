from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped

from neft_integration_hub.db import Base


class EdoStubStatus(str, Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    SIGNED = "SIGNED"
    REJECTED = "REJECTED"


class EdoStubDocument(Base):
    __tablename__ = "edo_stub_documents"
    __table_args__ = (Index("ix_edo_stub_documents_status", "status"),)

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = Column(String(64), nullable=False, index=True)
    counterparty: Mapped[dict] = Column(JSON, nullable=False)
    payload_ref: Mapped[str] = Column(String(255), nullable=False)
    status: Mapped[str] = Column(String(32), nullable=False)
    meta: Mapped[dict | None] = Column(JSON, nullable=True)

    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_status_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)


class EdoStubEvent(Base):
    __tablename__ = "edo_stub_events"
    __table_args__ = (Index("ix_edo_stub_events_doc", "edo_document_id", "created_at"),)

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    edo_document_id: Mapped[str] = Column(String(36), nullable=False, index=True)
    status: Mapped[str] = Column(String(32), nullable=False)
    note: Mapped[str | None] = Column(Text, nullable=True)
    payload: Mapped[dict | None] = Column(JSON, nullable=True)

    created_at: Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["EdoStubDocument", "EdoStubEvent", "EdoStubStatus"]

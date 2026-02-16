from __future__ import annotations

import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db.types import GUID


class DocType(str, enum.Enum):
    CHARTER = "CHARTER"
    EGRUL = "EGRUL"
    PASSPORT = "PASSPORT"
    POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
    BANK_DETAILS = "BANK_DETAILS"
    OTHER = "OTHER"


class DocStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ClientDocument(Base):
    __tablename__ = "client_documents"
    __table_args__ = (
        Index("ix_client_documents_application_id", "client_application_id"),
        Index("ix_client_documents_doc_type", "doc_type"),
        Index("ix_client_documents_status", "status"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_application_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("client_onboarding_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=DocStatus.UPLOADED.value)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

from __future__ import annotations

import enum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db.types import GUID


class GeneratedDocKind(str, enum.Enum):
    OFFER = "OFFER"
    SERVICE_AGREEMENT = "SERVICE_AGREEMENT"
    DPA = "DPA"
    APP_FORM = "APP_FORM"


class GeneratedDocStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SIGNED_BY_PLATFORM = "SIGNED_BY_PLATFORM"
    SIGNED_BY_CLIENT = "SIGNED_BY_CLIENT"


class ClientGeneratedDocument(Base):
    __tablename__ = "client_generated_documents"
    __table_args__ = (
        Index("ix_client_generated_documents_application_id", "client_application_id"),
        Index("ix_client_generated_documents_client_id", "client_id"),
        UniqueConstraint("client_application_id", "doc_kind", "version", name="uq_client_generated_docs_app_kind_version"),
        UniqueConstraint("client_id", "doc_kind", "version", name="uq_client_generated_docs_client_kind_version"),
        CheckConstraint(
            "(client_application_id IS NOT NULL) OR (client_id IS NOT NULL)",
            name="ck_client_generated_docs_owner_set",
        ),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_application_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey("client_onboarding_applications.id", ondelete="CASCADE"),
        nullable=True,
    )
    client_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("clients.id"), nullable=True)
    doc_kind: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False, default="application/pdf")
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    template_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

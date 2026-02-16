from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db.types import GUID


class ClientDocumentPackage(Base):
    __tablename__ = "client_document_packages"
    __table_args__ = (
        Index("ix_client_document_packages_client_created", "client_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    application_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    package_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ClientDocumentPackageItem(Base):
    __tablename__ = "client_document_package_items"
    __table_args__ = (
        Index("ix_client_document_package_items_package_id", "package_id"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    package_id: Mapped[str] = mapped_column(GUID(), ForeignKey("client_document_packages.id", ondelete="CASCADE"), nullable=False)
    doc_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("client_generated_documents.id", ondelete="SET NULL"), nullable=True)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


JSON_TYPE = JSON().with_variant(JSONB(none_as_null=True), "postgresql")


class ClientDocflowNotification(Base):
    __tablename__ = "client_docflow_notifications"
    __table_args__ = (
        Index("ix_client_docflow_notifications_client_created", "client_id", "created_at"),
        Index("ix_client_docflow_notifications_client_read", "client_id", "read_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    read_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meta_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)

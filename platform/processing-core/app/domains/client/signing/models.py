from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.db.types import GUID


class ClientDocSignRequest(Base):
    __tablename__ = "client_doc_sign_requests"
    __table_args__ = (
        Index("ix_client_doc_sign_requests_doc_id", "doc_id"),
        Index("ix_client_doc_sign_requests_status", "status"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("client_generated_documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"), default=5)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("ix_otp_challenges_user_id_created_at", "user_id", "created_at"),
        Index("ix_otp_challenges_document_id", "document_id"),
        Index(
            "uq_otp_challenges_active_document_user",
            "document_id",
            "user_id",
            unique=True,
            postgresql_where=text("status in ('PENDING','SENT','CONFIRMED')"),
        ),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'DOC_SIGN'"))
    document_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("client_generated_documents.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    salt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'PENDING'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"), default=5)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    resend_available_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClientAuditEvent(Base):
    __tablename__ = "client_audit_events"
    __table_args__ = (
        Index("ix_client_audit_events_doc_id", "doc_id"),
        Index("ix_client_audit_events_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    application_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    doc_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    actor_type: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

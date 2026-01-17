from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class EmailOutboxStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_status_retry", "status", "next_retry_at"),
        Index("ix_email_outbox_idempotency", "idempotency_key", unique=True),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(String(64), nullable=True)
    user_id = Column(String(64), nullable=True)
    idempotency_key = Column(String(256), nullable=False, unique=True)
    to_emails = Column(JSON, nullable=False)
    subject = Column(String(256), nullable=False)
    text_body = Column(Text, nullable=False)
    html_body = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    template_key = Column(String(128), nullable=True)
    status = Column(
        ExistingEnum(EmailOutboxStatus, name="email_outbox_status"),
        nullable=False,
        default=EmailOutboxStatus.QUEUED,
    )
    attempts_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    provider = Column(String(64), nullable=True)
    provider_message_id = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)


__all__ = ["EmailOutbox", "EmailOutboxStatus"]

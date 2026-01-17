from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str

JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class HelpdeskProvider(str, Enum):
    ZENDESK = "zendesk"
    JIRA_SM = "jira_sm"


class HelpdeskIntegrationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class HelpdeskTicketLinkStatus(str, Enum):
    LINKED = "LINKED"
    FAILED = "FAILED"


class HelpdeskOutboxStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class HelpdeskOutboxEventType(str, Enum):
    TICKET_CREATED = "TICKET_CREATED"
    COMMENT_ADDED = "COMMENT_ADDED"
    TICKET_CLOSED = "TICKET_CLOSED"


class HelpdeskIntegration(Base):
    __tablename__ = "helpdesk_integrations"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="uq_helpdesk_integrations_scope"),
        Index("ix_helpdesk_integrations_org", "org_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False)
    provider = Column(ExistingEnum(HelpdeskProvider, name="helpdesk_provider"), nullable=False)
    status = Column(ExistingEnum(HelpdeskIntegrationStatus, name="helpdesk_integration_status"), nullable=False)
    config_json = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HelpdeskTicketLink(Base):
    __tablename__ = "helpdesk_ticket_links"
    __table_args__ = (
        UniqueConstraint("provider", "internal_ticket_id", name="uq_helpdesk_ticket_links_scope"),
        Index("ix_helpdesk_ticket_links_org", "org_id"),
        Index("ix_helpdesk_ticket_links_ticket", "internal_ticket_id"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False)
    internal_ticket_id = Column(GUID(), nullable=False)
    provider = Column(ExistingEnum(HelpdeskProvider, name="helpdesk_provider"), nullable=False)
    external_ticket_id = Column(String(128), nullable=True)
    external_url = Column(Text, nullable=True)
    status = Column(ExistingEnum(HelpdeskTicketLinkStatus, name="helpdesk_ticket_link_status"), nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HelpdeskOutbox(Base):
    __tablename__ = "helpdesk_outbox"
    __table_args__ = (
        Index("ix_helpdesk_outbox_org", "org_id"),
        Index("ix_helpdesk_outbox_status", "status"),
        Index("ix_helpdesk_outbox_retry", "next_retry_at"),
    )

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False)
    provider = Column(ExistingEnum(HelpdeskProvider, name="helpdesk_provider"), nullable=False)
    internal_ticket_id = Column(GUID(), nullable=False)
    event_type = Column(ExistingEnum(HelpdeskOutboxEventType, name="helpdesk_outbox_event_type"), nullable=False)
    payload_json = Column(JSON_TYPE, nullable=True)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    status = Column(ExistingEnum(HelpdeskOutboxStatus, name="helpdesk_outbox_status"), nullable=False)
    attempts_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)


__all__ = [
    "HelpdeskIntegration",
    "HelpdeskIntegrationStatus",
    "HelpdeskOutbox",
    "HelpdeskOutboxEventType",
    "HelpdeskOutboxStatus",
    "HelpdeskProvider",
    "HelpdeskTicketLink",
    "HelpdeskTicketLinkStatus",
]

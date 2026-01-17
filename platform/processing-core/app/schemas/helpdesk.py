from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.helpdesk import (
    HelpdeskIntegrationStatus,
    HelpdeskOutboxEventType,
    HelpdeskOutboxStatus,
    HelpdeskProvider,
    HelpdeskTicketLinkStatus,
)


class HelpdeskIntegrationConfig(BaseModel):
    base_url: str = Field(..., min_length=1)
    api_email: str | None = None
    api_token: str | None = None
    project_id: str | None = None
    brand_id: str | None = None


class HelpdeskIntegrationConfigPatch(BaseModel):
    base_url: str | None = Field(None, min_length=1)
    api_email: str | None = None
    api_token: str | None = None
    project_id: str | None = None
    brand_id: str | None = None


class HelpdeskIntegrationUpsert(BaseModel):
    provider: HelpdeskProvider = HelpdeskProvider.ZENDESK
    config: HelpdeskIntegrationConfig


class HelpdeskIntegrationPatch(BaseModel):
    provider: HelpdeskProvider | None = None
    config: HelpdeskIntegrationConfigPatch | None = None


class HelpdeskIntegrationOut(BaseModel):
    id: str
    org_id: str
    provider: HelpdeskProvider
    status: HelpdeskIntegrationStatus
    base_url: str | None = None
    project_id: str | None = None
    brand_id: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class HelpdeskIntegrationResponse(BaseModel):
    integration: HelpdeskIntegrationOut | None = None


class HelpdeskTicketLinkOut(BaseModel):
    id: str
    org_id: str
    internal_ticket_id: str
    provider: HelpdeskProvider
    external_ticket_id: str | None = None
    external_url: str | None = None
    status: HelpdeskTicketLinkStatus
    last_sync_at: datetime | None = None


class HelpdeskTicketLinkResponse(BaseModel):
    link: HelpdeskTicketLinkOut | None = None


class HelpdeskOutboxOut(BaseModel):
    id: str
    org_id: str
    provider: HelpdeskProvider
    internal_ticket_id: str
    event_type: HelpdeskOutboxEventType
    status: HelpdeskOutboxStatus
    attempts_count: int
    last_error: str | None = None
    next_retry_at: datetime | None = None
    created_at: datetime
    sent_at: datetime | None = None


__all__ = [
    "HelpdeskIntegrationConfig",
    "HelpdeskIntegrationConfigPatch",
    "HelpdeskIntegrationPatch",
    "HelpdeskIntegrationResponse",
    "HelpdeskIntegrationOut",
    "HelpdeskIntegrationUpsert",
    "HelpdeskOutboxOut",
    "HelpdeskTicketLinkOut",
    "HelpdeskTicketLinkResponse",
]

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminAuditEvent(BaseModel):
    id: str | None = None
    ts: datetime | None = None
    type: str | None = None
    action: str | None = None
    title: str | None = None
    actor: str | None = None
    actor_type: str | None = None
    reason: str | None = None
    correlation_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    meta: dict | None = None
    payload: dict | None = None


class AdminAuditFeedResponse(BaseModel):
    items: list[AdminAuditEvent]
    total: int | None = None
    limit: int | None = None
    offset: int | None = None


class AdminAuditCorrelationResponse(BaseModel):
    correlation_id: str
    items: list[AdminAuditEvent] | None = None
    events: list[AdminAuditEvent] | None = None
    chain: list[str] | None = None

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogOut(BaseModel):
    id: str
    ts: datetime
    tenant_id: int | None = None
    actor_type: str
    actor_id: str | None = None
    actor_email: str | None = None
    actor_roles: list[str] | None = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    diff: dict | None = None
    external_refs: dict | None = None
    reason: str | None = None
    attachment_key: str | None = None
    prev_hash: str
    hash: str

    model_config = ConfigDict(from_attributes=True)


class AuditSearchResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class AuditVerifyRequest(BaseModel):
    from_ts: datetime = Field(..., alias="from")
    to_ts: datetime = Field(..., alias="to")
    tenant_id: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class AuditVerifyResponse(BaseModel):
    status: str
    checked: int
    broken_at_id: str | None = None
    message: str | None = None


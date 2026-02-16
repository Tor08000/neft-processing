from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .common import ORMModel


class AuditEventOut(ORMModel):
    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_type: str
    actor_id: str | None
    actor_email: str | None
    request_id: str | None
    diff: dict
    created_at: datetime


class AuditListOut(BaseModel):
    items: list[AuditEventOut]
    limit: int
    offset: int
    total: int

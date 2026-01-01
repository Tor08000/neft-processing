from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit_retention import AuditLegalHoldScope


class AuditLegalHoldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: AuditLegalHoldScope
    case_id: str | None = None
    reason: str


class AuditLegalHoldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: AuditLegalHoldScope
    case_id: str | None
    reason: str
    created_by: str | None
    created_at: datetime
    active: bool


__all__ = ["AuditLegalHoldCreate", "AuditLegalHoldOut"]

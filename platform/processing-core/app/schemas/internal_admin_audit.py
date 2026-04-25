from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class AdminUserAuditIngestRequest(BaseModel):
    action: Literal["create", "update"]
    user_id: str
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None
    correlation_id: str | None = None

    @field_validator("reason", "correlation_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class AdminUserAuditIngestResponse(BaseModel):
    status: Literal["ok"]
    audit_id: str

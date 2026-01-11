from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.service_identities import ServiceIdentityStatus, ServiceTokenStatus


class ServiceIdentityCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(..., min_length=3, max_length=128)
    description: str | None = None
    status: ServiceIdentityStatus = ServiceIdentityStatus.ACTIVE


class ServiceIdentityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    service_name: str
    description: str | None = None
    status: ServiceIdentityStatus
    created_at: datetime
    updated_at: datetime


class ServiceTokenOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    service_identity_id: str
    prefix: str
    scopes: list[str]
    issued_at: datetime
    expires_at: datetime
    rotated_from_id: str | None
    rotation_grace_until: datetime | None
    last_used_at: datetime | None
    status: ServiceTokenStatus


class ServiceTokenIssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopes: list[str]
    expires_at: datetime
    env: str = Field(default="live", pattern="^(live|test)$")


class ServiceTokenIssueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    token_id: str
    prefix: str
    scopes: list[str]
    expires_at: datetime


class ServiceTokenRotateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grace_hours: int | None = Field(default=None, ge=0, le=168)
    expires_at: datetime | None = None
    env: str = Field(default="live", pattern="^(live|test)$")


class ServiceTokenRevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


__all__ = [
    "ServiceIdentityCreateIn",
    "ServiceIdentityOut",
    "ServiceTokenIssueIn",
    "ServiceTokenIssueOut",
    "ServiceTokenOut",
    "ServiceTokenRotateIn",
    "ServiceTokenRevokeIn",
]

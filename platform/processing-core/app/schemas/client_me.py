from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic import field_validator
from zoneinfo import ZoneInfo


class ClientMeUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str | None = None
    subject_type: str | None = None
    timezone: str | None = None


class ClientMeOrg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    inn: str | None = None
    status: str
    timezone: str | None = None


class ClientMeMembership(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str]
    status: str


class ClientMeSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str
    status: str | None = None
    modules: dict[str, dict[str, Any]]
    limits: dict[str, dict[str, Any]]


class ClientMeEntitlements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled_modules: list[str]
    permissions: list[str]
    limits: dict[str, dict[str, Any]]
    org_status: str


class ClientMeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: ClientMeUser
    org: ClientMeOrg | None = None
    membership: ClientMeMembership
    subscription: ClientMeSubscription | None = None
    entitlements: ClientMeEntitlements
    org_status: str


class ClientAccountTimezoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:  # noqa: D417
        try:
            ZoneInfo(v)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid_timezone") from exc
        return v

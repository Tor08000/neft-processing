from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ROLE_CHOICES = [
    "PLATFORM_ADMIN",
    "CLIENT_OWNER",
    "CLIENT_MANAGER",
    "CLIENT_VIEWER",
]


def _normalize_email(value: str) -> str:
    value = value.strip()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("invalid email format")
    return value.lower()


def _validate_roles(values: list[str]) -> list[str]:
    invalid = [v for v in values if v not in ROLE_CHOICES]
    if invalid:
        raise ValueError(f"invalid roles: {', '.join(invalid)}")
    return values


class AdminUserBase(BaseModel):
    email: str
    full_name: str | None = None
    is_active: bool | None = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)


class AdminUserCreateRequest(AdminUserBase):
    password: str = Field(min_length=6)
    roles: list[Literal[*ROLE_CHOICES]]

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:  # noqa: D417
        return _validate_roles(v)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    roles: list[Literal[*ROLE_CHOICES]] | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str] | None) -> list[str] | None:  # noqa: D417
        if v is None:
            return v
        return _validate_roles(v)


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    roles: list[str]

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)

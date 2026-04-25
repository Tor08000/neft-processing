from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ROLE_CHOICES = [
    "ADMIN",
    "SUPERADMIN",
    "NEFT_ADMIN",
    "NEFT_SUPERADMIN",
    "PLATFORM_ADMIN",
    "NEFT_FINANCE",
    "FINANCE",
    "ADMIN_FINANCE",
    "NEFT_SUPPORT",
    "SUPPORT",
    "NEFT_OPS",
    "OPS",
    "OPERATIONS",
    "NEFT_SALES",
    "SALES",
    "CRM",
    "ADMIN_CRM",
    "NEFT_LEGAL",
    "LEGAL",
    "ANALYST",
    "AUDITOR",
    "OBSERVER",
    "READ_ONLY_ANALYST",
    "NEFT_OBSERVER",
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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


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
    roles: list[str]
    reason: str | None = None
    correlation_id: str | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:  # noqa: D417
        return _validate_roles(v)

    @field_validator("reason", "correlation_id")
    @classmethod
    def normalize_optional_text(cls, v: str | None) -> str | None:  # noqa: D417
        return _normalize_optional_text(v)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    roles: list[str] | None = None
    reason: str | None = None
    correlation_id: str | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str] | None) -> list[str] | None:  # noqa: D417
        if v is None:
            return v
        return _validate_roles(v)

    @field_validator("reason", "correlation_id")
    @classmethod
    def normalize_optional_text(cls, v: str | None) -> str | None:  # noqa: D417
        return _normalize_optional_text(v)


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    roles: list[str]

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, v) -> str:  # noqa: D417
        return str(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)

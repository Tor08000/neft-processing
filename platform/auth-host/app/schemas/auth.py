from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


def _normalize_email(value: str) -> str:
    value = value.strip()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("invalid email format")
    return value.lower()


class HealthResponse(BaseModel):
    status: str
    service: str
    reason: str | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str
    portal: str | None = Field(default=None, description="client, admin, or partner")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email: str
    subject_type: str = Field(default="user", description="Тип субъекта в токене")
    client_id: str | None = Field(default=None, description="Организация клиента")
    roles: list[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)


class AuthMeResponse(BaseModel):
    email: str
    roles: list[str]
    subject: str
    subject_type: str = "user"
    client_id: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:  # noqa: D417
        return _normalize_email(v)

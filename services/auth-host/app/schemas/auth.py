from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ClientLoginRequest(BaseModel):
    email: EmailStr
    password: str
    client_id: str | None = Field(
        default=None, description="Идентификатор организации клиента, если известен"
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email: EmailStr
    subject_type: str = Field(default="user", description="Тип субъекта в токене")
    client_id: str | None = Field(default=None, description="Организация клиента")


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class AuthMeResponse(BaseModel):
    email: EmailStr
    roles: list[str]
    subject: str
    subject_type: str = "user"
    client_id: str | None = None

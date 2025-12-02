from __future__ import annotations

import hashlib
import itertools
import os
from typing import Dict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.schemas.auth import (
    HealthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import create_access_token
from app.services.keys import get_public_key_pem
from neft_shared.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["auth"])

_users: Dict[str, UserResponse] = {}
_password_hashes: Dict[str, str] = {}
_user_sequence = itertools.count(1)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _admin_credentials() -> tuple[str, str]:
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    return email, password


def _ensure_user_record(email: str) -> UserResponse:
    if email in _users:
        return _users[email]

    next_id = next(_user_sequence)
    user = UserResponse(
        id=next_id,
        email=email,
        full_name=None,
        is_active=True,
        created_at=None,
    )
    _users[email] = user
    return user


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="auth-host")


@router.get("/auth/public-key", response_class=PlainTextResponse)
async def public_key() -> str:
    """Возвращаем публичный ключ для проверки JWT."""

    return get_public_key_pem()


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> UserResponse:
    admin_email, _ = _admin_credentials()
    if payload.email.lower() == admin_email.lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin_email_reserved")

    if payload.email in _users:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

    password_hash = _hash_password(payload.password)
    _password_hashes[payload.email] = password_hash

    user = _ensure_user_record(payload.email)
    user.full_name = payload.full_name
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    admin_email, admin_password = _admin_credentials()

    if payload.email.lower() == admin_email.lower():
        if payload.password != admin_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        roles = ["ADMIN"]
    else:
        expected_hash = _password_hashes.get(payload.email)
        if not expected_hash or expected_hash != _hash_password(payload.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        roles = []

    settings = get_settings()
    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRES_IN", settings.access_token_expires_min * 60))
    token = create_access_token(payload.email, roles=roles)

    user = _ensure_user_record(payload.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        email=user.email,
    )

from __future__ import annotations

import itertools
import os
from typing import Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.schemas.auth import (
    AuthMeResponse,
    ClientLoginRequest,
    HealthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    security_scheme,
    verify_password,
)
from app.services.keys import get_public_key_pem
from neft_shared.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["auth"])

_users: Dict[str, UserResponse] = {}
_password_hashes: Dict[str, str] = {}
_user_sequence = itertools.count(1)

_client_users: Dict[str, Tuple[str, UserResponse]] = {}

DEMO_CLIENT_EMAIL = os.getenv("DEMO_CLIENT_EMAIL", "demo@client.neft")
DEMO_CLIENT_PASSWORD = os.getenv("DEMO_CLIENT_PASSWORD", "Demo123!")
DEMO_CLIENT_ID = os.getenv("DEMO_CLIENT_ID", "demo-client")
DEMO_CLIENT_FULL_NAME = os.getenv("DEMO_CLIENT_FULL_NAME", "Demo Client")


def _bootstrap_demo_client():
    if DEMO_CLIENT_EMAIL and DEMO_CLIENT_PASSWORD:
        _password_hashes[DEMO_CLIENT_EMAIL] = hash_password(DEMO_CLIENT_PASSWORD)
        user = _ensure_client_user(DEMO_CLIENT_EMAIL, client_id=DEMO_CLIENT_ID)
        user.full_name = DEMO_CLIENT_FULL_NAME


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


def _ensure_client_user(email: str, client_id: str | None = None) -> UserResponse:
    if email in _client_users:
        _, user = _client_users[email]
        return user

    next_id = next(_user_sequence)
    user = UserResponse(
        id=next_id,
        email=email,
        full_name=None,
        is_active=True,
        created_at=None,
    )
    resolved_client_id = client_id or "demo-client"
    _client_users[email] = (resolved_client_id, user)
    return user


_bootstrap_demo_client()


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

    password_hash = hash_password(payload.password)
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
        if not expected_hash or not verify_password(payload.password, expected_hash):
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
        subject_type="user",
    )


@router.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> AuthMeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    roles = payload.get("roles") or []
    client_id = payload.get("client_id")
    subject_type = payload.get("subject_type", "user")
    return AuthMeResponse(
        email=subject,
        roles=roles,
        subject=subject,
        subject_type=subject_type,
        client_id=client_id,
    )


@router.post(
    "/client/api/v1/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
)
async def register_client(payload: RegisterRequest) -> UserResponse:
    if payload.email in _client_users:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client_user_exists")

    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="client_registration_disabled",
    )


@router.post("/client/api/v1/auth/login", response_model=TokenResponse)
async def login_client(payload: ClientLoginRequest) -> TokenResponse:
    if payload.email.lower() != DEMO_CLIENT_EMAIL.lower():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    expected_hash = _password_hashes.get(DEMO_CLIENT_EMAIL)
    if not expected_hash or not verify_password(payload.password, expected_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = _ensure_client_user(DEMO_CLIENT_EMAIL, client_id=DEMO_CLIENT_ID)

    settings = get_settings()
    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRES_IN", settings.access_token_expires_min * 60))
    client_id = payload.client_id or DEMO_CLIENT_ID
    token = create_access_token(
        DEMO_CLIENT_EMAIL,
        roles=["CLIENT_USER"],
        subject_type="client_user",
        client_id=client_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        email=user.email,
        subject_type="client_user",
        client_id=client_id,
    )


@router.get("/client/api/v1/auth/me", response_model=AuthMeResponse)
async def client_auth_me(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> AuthMeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    roles = payload.get("roles") or []
    client_id = payload.get("client_id")
    subject_type = payload.get("subject_type", "client_user")
    return AuthMeResponse(
        email=subject,
        roles=roles,
        subject=subject,
        subject_type=subject_type,
        client_id=client_id,
    )

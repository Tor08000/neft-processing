from __future__ import annotations

import itertools
import os
from typing import Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.db import get_conn
from app.schemas.auth import (
    AuthMeResponse,
    ClientLoginRequest,
    HealthResponse,
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

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

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


async def _find_client_id(email: str) -> Tuple[str | None, str | None]:
    async with get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT id, full_name FROM clients WHERE lower(email) = lower(%s) LIMIT 1",
            (email,),
        )
        row = await cur.fetchone()
        if not row:
            return None, None
        return str(row["id"]), row.get("full_name") if isinstance(row, dict) else row[1]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="auth-host")


@router.get("/public-key", response_class=PlainTextResponse)
async def public_key() -> str:
    """Возвращаем публичный ключ для проверки JWT."""

    return get_public_key_pem()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/login", response_model=TokenResponse)
async def login(payload: ClientLoginRequest) -> TokenResponse:
    admin_email, admin_password = _admin_credentials()
    email_lower = payload.email.lower()

    subject_type = "user"
    client_id: str | None = None
    client_full_name: str | None = None

    if email_lower == admin_email.lower():
        if payload.password != admin_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        roles = ["ADMIN"]
        user = _ensure_user_record(payload.email)
    elif email_lower == DEMO_CLIENT_EMAIL.lower():
        expected_hash = _password_hashes.get(DEMO_CLIENT_EMAIL)
        if not expected_hash or not verify_password(payload.password, expected_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        client_id, client_full_name = await _find_client_id(DEMO_CLIENT_EMAIL)
        if not client_id:
            client_id = payload.client_id or DEMO_CLIENT_ID
        if not client_full_name:
            client_full_name = DEMO_CLIENT_FULL_NAME
        user = _ensure_client_user(DEMO_CLIENT_EMAIL, client_id=client_id)
        user.full_name = client_full_name
        roles = ["CLIENT_USER"]
        subject_type = "client_user"
    else:
        expected_hash = _password_hashes.get(payload.email)
        if not expected_hash or not verify_password(payload.password, expected_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        client_id, client_full_name = await _find_client_id(payload.email)
        if client_id:
            user = _ensure_client_user(payload.email, client_id=client_id)
            user.full_name = client_full_name
            roles = ["CLIENT_USER"]
            subject_type = "client_user"
        else:
            user = _ensure_user_record(payload.email)
            roles = []

    settings = get_settings()
    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRES_IN", settings.access_token_expires_min * 60))
    token = create_access_token(
        payload.email,
        roles=roles,
        subject_type=subject_type,
        client_id=client_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        email=user.email,
        subject_type=subject_type,
        client_id=client_id,
    )


@router.get("/me", response_model=AuthMeResponse)
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



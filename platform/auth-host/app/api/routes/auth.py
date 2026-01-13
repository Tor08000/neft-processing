from __future__ import annotations

import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.db import get_conn
from app.models import User
from app.schemas.auth import (
    AuthMeResponse,
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
from app.settings import get_settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _admin_credentials() -> tuple[str, str]:
    """
    Optional bootstrap admin credentials.
    If not set, returns empty values.
    """
    settings = get_settings()
    email = os.getenv("AUTH_ADMIN_EMAIL") or settings.bootstrap_admin_email or settings.demo_admin_email
    password = os.getenv("AUTH_ADMIN_PASSWORD") or settings.bootstrap_admin_password or ""
    return email, password


async def _get_user_from_db(email: str) -> User | None:
    email_normalized = email.strip().lower()

    async with get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT id, email, full_name, password_hash, is_active, created_at "
            "FROM users WHERE lower(email) = lower(%s) LIMIT 1",
            (email_normalized,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return User.from_row(row)


async def _get_roles_for_user(user_id: str) -> list[str]:
    async with get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT role_code FROM user_roles WHERE user_id = %s",
            (user_id,),
        )
        roles_rows = await cur.fetchall()
    return [row["role_code"] for row in roles_rows]


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
    admin_email = admin_email.strip().lower() if admin_email else ""

    normalized_email = payload.email.strip().lower()

    if admin_email and normalized_email == admin_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin_email_reserved")

    existing = await _get_user_from_db(payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

    password_hash = hash_password(payload.password)
    new_user_id = uuid4()
    async with get_conn() as (conn, cur):
        await cur.execute(
            "INSERT INTO users (id, email, full_name, password_hash) VALUES (%s, %s, %s, %s)"
            " RETURNING id, email, full_name, password_hash, is_active, created_at",
            (new_user_id, payload.email, payload.full_name, password_hash),
        )
        row = await cur.fetchone()
        await conn.commit()

    user = User.from_row(row)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    normalized_email = payload.email.strip().lower()

    subject_type = "user"
    user_email = normalized_email

    logger.info(
        "login attempt: email=%s -> normalized=%s", payload.email, normalized_email
    )

    try:
        user = await _get_user_from_db(normalized_email)
    except Exception:
        logger.exception(
            "Failed to fetch user during login", extra={"email": normalized_email}
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error")

    logger.info(
        "login attempt: email=%s -> normalized=%s, user_found=%s",
        payload.email,
        normalized_email,
        bool(user),
    )

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    roles = await _get_roles_for_user(user.id)
    user_email = user.email

    settings = get_settings()
    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRES_IN", settings.access_token_expires_min * 60))
    token = create_access_token(
        user_email,
        roles=roles,
        subject_type=subject_type,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        email=user_email,
        subject_type=subject_type,
        roles=roles,
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

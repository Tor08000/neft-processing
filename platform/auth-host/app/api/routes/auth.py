from __future__ import annotations

import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
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
from app.healthcheck import build_health_response
from app.services.keys import InvalidRSAKeyError, get_public_key_pem, get_public_jwk
from app.settings import get_settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _admin_credentials() -> tuple[str, str]:
    """
    Optional bootstrap admin credentials.
    If not set, returns empty values.
    """
    settings = get_settings()
    email = settings.bootstrap_admin_email or settings.demo_admin_email
    password = settings.bootstrap_admin_password or ""
    return email, password


def _resolve_portal(value: str | None) -> str | None:
    portal = (value or "").strip().lower()
    if not portal:
        return None
    if portal in {"client", "admin", "partner"}:
        return portal
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_portal")


def _resolve_login_portal(request: Request, payload: LoginRequest) -> str:
    portal = _resolve_portal(payload.portal)
    if portal:
        return portal
    portal = _resolve_portal(request.headers.get("X-Portal"))
    if portal:
        return portal
    portal = _resolve_portal(request.query_params.get("portal"))
    if portal:
        return portal
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "portal_required", "reason_code": "PORTAL_REQUIRED"},
    )


def _is_dev_env() -> bool:
    env = (os.getenv("NEFT_ENV") or "local").lower()
    return env in {"local", "dev", "development", "test"}


def _portal_token_config(portal: str) -> tuple[str, str]:
    settings = get_settings()
    if portal == "client":
        return settings.auth_client_issuer, settings.auth_client_audience
    return settings.auth_issuer, settings.auth_audience


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
    response, status_code = build_health_response()
    content = response.model_dump(exclude_none=True)
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=content)
    return JSONResponse(status_code=status_code, content=content)


@router.get("/public-key", response_class=PlainTextResponse)
async def public_key() -> str:
    """Возвращаем публичный ключ для проверки JWT."""

    try:
        return get_public_key_pem()
    except InvalidRSAKeyError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rsa_keys_unavailable")


@router.get("/.well-known/jwks.json", include_in_schema=False)
async def jwks() -> dict:
    return {"keys": [get_public_jwk()]}


@router.get("/jwks", include_in_schema=False)
async def jwks_legacy() -> RedirectResponse:
    return RedirectResponse(url="/api/v1/auth/.well-known/jwks.json", status_code=status.HTTP_308_PERMANENT_REDIRECT)


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
        await cur.execute(
            "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (new_user_id, "CLIENT_OWNER"),
        )
        await conn.commit()

    user = User.from_row(row)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: RegisterRequest) -> UserResponse:
    return await register(payload)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest) -> TokenResponse:
    normalized_email = payload.email.strip().lower()
    portal = _resolve_login_portal(request, payload)

    subject_type = "user"
    user_email = normalized_email
    client_id = None
    org_id = None

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
    expires_in = settings.access_token_expires_min * 60
    issuer, audience = _portal_token_config(portal)
    if portal == "client":
        subject_type = "client_user"
        if _is_dev_env():
            client_id = settings.demo_client_uuid
            org_id = settings.demo_org_id
    try:
        token = create_access_token(
            user_email,
            roles=roles,
            subject_type=subject_type,
            client_id=client_id,
            user_id=str(user.id),
            org_id=org_id,
            issuer=issuer,
            audience=audience,
        )
    except InvalidRSAKeyError:
        logger.error("RSA keys unavailable during login", extra={"email": normalized_email})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rsa_keys_unavailable")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        email=user_email,
        subject_type=subject_type,
        client_id=client_id,
        roles=roles,
    )


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> AuthMeResponse:
    if credentials is None:
        logger.info("auth_me unauthorized: missing token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    if credentials.scheme.lower() != "bearer":
        logger.info("auth_me unauthorized: invalid auth scheme", extra={"scheme": credentials.scheme})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    if not credentials.credentials:
        logger.info("auth_me unauthorized: empty bearer token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    portal = _resolve_portal(request.headers.get("X-Portal")) or "client"
    issuer, audience = _portal_token_config(portal)
    try:
        payload = decode_access_token(credentials.credentials, issuer=issuer, audience=audience)
    except HTTPException as exc:
        logger.info("auth_me unauthorized: invalid token", extra={"detail": exc.detail})
        raise
    subject = payload.get("sub")
    if not subject:
        logger.info("auth_me unauthorized: missing subject")
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

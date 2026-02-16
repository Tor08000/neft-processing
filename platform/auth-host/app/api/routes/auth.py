from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
from jose import JWTError, jwt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.adapters.oauth_providers import oidc_client
from app.db import DSN_ASYNC, get_conn
from app.models import User
from app.schemas.auth import (
    AuthMeResponse,
    HealthResponse,
    LoginRequest,
    RegisterRequest,
    SignupResponse,
    TokenResponse,
    RefreshRequest,
    RevokeUserTokensRequest,
    RevokeTenantTokensRequest,
    VerifyResponse,
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
CORE_DB_SCHEMA = os.getenv("NEFT_DB_SCHEMA", "processing_core")


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _device_key(request: Request) -> str:
    ua = (request.headers.get("user-agent") or "").strip()
    forwarded = (request.headers.get("x-forwarded-for") or request.client.host if request.client else "").strip()
    return hashlib.sha256(f"{ua}|{forwarded}".encode("utf-8")).hexdigest()


def _decode_refresh_token(refresh_token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(refresh_token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token") from exc
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")
    return payload


def _create_refresh_token(*, user_id: str, tenant_id: str, device_key: str, prev_jti: str | None = None) -> tuple[str, str, datetime]:
    settings = get_settings()
    exp = datetime.now(tz=timezone.utc) + timedelta(days=settings.refresh_token_expires_days)
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "typ": "refresh",
        "jti": jti,
        "exp": exp,
        "device_key": device_key,
    }
    if prev_jti:
        payload["rotated_from"] = prev_jti
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti, exp


async def _persist_refresh_token(*, user_id: str, tenant_id: str, refresh_token: str, expires_at: datetime, device_key: str, rotated_from: str | None = None) -> None:
    token_hash = _hash_refresh_token(refresh_token)
    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            INSERT INTO refresh_tokens (user_id, tenant_id, token_hash, expires_at, rotated_from, device_key)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, tenant_id, token_hash, expires_at, rotated_from, device_key),
        )
        await conn.commit()




async def _resolve_tenant(*, request: Request, tenant_code: str | None = None) -> dict:
    code = (tenant_code or "").strip().lower()
    if not code:
        host = (request.headers.get("host") or "").split(":", 1)[0].strip().lower()
        if host and "." in host:
            code = host.split(".", 1)[0]
    if not code:
        code = "default"
    try:
        async with get_conn() as (_conn, cur):
            await cur.execute("SELECT id, code, name, sso_enforced, token_version FROM tenants WHERE code=%s LIMIT 1", (code,))
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
        return row
    except HTTPException:
        raise
    except Exception:
        return {"id": "00000000-0000-0000-0000-000000000000", "code": code, "name": code, "sso_enforced": False, "token_version": 1}


def _oidc_enabled_or_503() -> None:
    if not get_settings().oidc_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="oidc_disabled")


async def _core_table_exists(cur: psycopg.AsyncCursor, table_name: str) -> bool:
    await cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
        (CORE_DB_SCHEMA, table_name),
    )
    return await cur.fetchone() is not None


async def _create_core_client(*, user_id: str, email: str, full_name: str | None) -> str:
    client_id = str(uuid4())
    async with psycopg.AsyncConnection.connect(DSN_ASYNC) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(CORE_DB_SCHEMA))
            )
            if not await _core_table_exists(cur, "clients"):
                raise HTTPException(status_code=503, detail="core_clients_table_missing")
            if not await _core_table_exists(cur, "client_onboarding"):
                raise HTTPException(status_code=503, detail="core_onboarding_table_missing")

            display_name = full_name or email.split("@", 1)[0] or "Client"
            await cur.execute(
                "INSERT INTO clients (id, name, email, status) VALUES (%s, %s, %s, %s)",
                (client_id, display_name, email, "ONBOARDING"),
            )
            await cur.execute(
                "INSERT INTO client_onboarding (client_id, owner_user_id, step, status) VALUES (%s, %s, %s, %s)",
                (client_id, user_id, "PROFILE", "DRAFT"),
            )
            await conn.commit()
    return client_id


async def _get_client_id_for_user(user_id: str) -> str | None:
    try:
        async with get_conn() as (_conn, cur):
            await cur.execute(
                "SELECT client_id FROM user_clients WHERE user_id=%s",
                (user_id,),
            )
            row = await cur.fetchone()
            return row["client_id"] if row else None
    except Exception:
        return None




async def _get_tenant_token_version(tenant_id: str | None) -> int:
    if not tenant_id:
        return 1
    async with get_conn() as (_conn, cur):
        await cur.execute("SELECT token_version FROM tenants WHERE id=%s", (tenant_id,))
        row = await cur.fetchone()
    return int(row["token_version"]) if row else 1


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

    path = request.url.path.lower()
    if "/partner" in path:
        return "partner"
    if "/admin" in path:
        return "admin"
    return "client"


def _is_dev_env() -> bool:
    env = (os.getenv("NEFT_ENV") or "local").lower()
    return env in {"local", "dev", "development", "test"}


def _portal_token_config(portal: str) -> tuple[str, str]:
    settings = get_settings()
    if portal == "client":
        return settings.auth_client_issuer, settings.auth_client_audience
    if portal == "partner":
        return settings.auth_partner_issuer, settings.auth_partner_audience
    return settings.auth_issuer, settings.auth_audience


async def _get_user_from_db(*, tenant_id: str | None = None, email: str | None = None, username: str | None = None) -> User | None:
    normalized_email = email.strip().lower() if email else None
    normalized_username = username.strip().lower() if username else None

    if not normalized_email and not normalized_username:
        return None

    async with get_conn() as (_conn, cur):
        if normalized_email:
            if tenant_id:
                await cur.execute(
                    "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at "
                    "FROM users WHERE tenant_id=%s AND lower(email) = lower(%s) LIMIT 1",
                    (tenant_id, normalized_email),
                )
            else:
                await cur.execute(
                    "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at "
                    "FROM users WHERE lower(email) = lower(%s) LIMIT 1",
                    (normalized_email,),
                )
        else:
            if tenant_id:
                await cur.execute(
                    "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at "
                    "FROM users WHERE tenant_id=%s AND lower(username) = lower(%s) LIMIT 1",
                    (tenant_id, normalized_username),
                )
            else:
                await cur.execute(
                    "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at "
                    "FROM users WHERE lower(username) = lower(%s) LIMIT 1",
                    (normalized_username,),
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


async def _upsert_user_roles(user_id: str, roles: list[str]) -> None:
    async with get_conn() as (conn, cur):
        await cur.execute("DELETE FROM user_roles WHERE user_id=%s", (user_id,))
        for role in sorted({r for r in roles if r}):
            await cur.execute(
                "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, role),
            )
        await conn.commit()


async def _resolve_or_create_oauth_user(*, tenant_id: str, provider_id: str | None, provider_name: str, claims: dict) -> User:
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="oidc_email_required")

    provider_user_id = str(claims.get("sub") or "").strip()
    if not provider_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="oidc_subject_required")

    full_name = claims.get("name")

    async with get_conn() as (conn, cur):
        if provider_id:
            await cur.execute(
                """
                SELECT u.id, u.tenant_id, u.email, u.username, u.full_name, u.password_hash, u.is_active, u.status, u.token_version, u.created_at
                FROM oauth_identities oi
                JOIN users u ON u.id = oi.user_id
                WHERE oi.provider_id=%s AND oi.provider_user_id=%s
                LIMIT 1
                """,
                (provider_id, provider_user_id),
            )
            row = await cur.fetchone()
            if row:
                return User.from_row(row)

        await cur.execute(
            """
            SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at
            FROM users
            WHERE tenant_id=%s AND lower(email)=lower(%s)
            LIMIT 1
            """,
            (tenant_id, email),
        )
        row = await cur.fetchone()
        if row:
            user = User.from_row(row)
        else:
            user_id = uuid4()
            password_hash = hash_password(uuid4().hex)
            await cur.execute(
                """
                INSERT INTO users (id, tenant_id, email, full_name, password_hash)
                VALUES (%s, %s, %s, %s)
                RETURNING id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at
                """,
                (user_id, tenant_id, email, full_name, password_hash),
            )
            row = await cur.fetchone()
            user = User.from_row(row)

        await cur.execute(
            """
            INSERT INTO oauth_identities (user_id, provider_id, provider_name, provider_user_id, email)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (provider_name, provider_user_id) DO NOTHING
            """,
            (user.id, provider_id, provider_name, provider_user_id, email),
        )
        await conn.commit()
    return user


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


@router.post("/register", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, payload: RegisterRequest) -> SignupResponse:
    admin_email, _ = _admin_credentials()
    admin_email = admin_email.strip().lower() if admin_email else ""

    normalized_email = payload.email.strip().lower()

    if admin_email and normalized_email == admin_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin_email_reserved")

    tenant = await _resolve_tenant(request=request)
    existing = await _get_user_from_db(tenant_id=str(tenant["id"]), email=payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

    password_hash = hash_password(payload.password)
    new_user_id = uuid4()
    async with get_conn() as (conn, cur):
        try:
            await cur.execute(
                "INSERT INTO users (id, tenant_id, email, full_name, password_hash) VALUES (%s, %s, %s, %s, %s)"
                " RETURNING id, email, full_name, password_hash, is_active, created_at",
                (new_user_id, tenant["id"], payload.email, payload.full_name, password_hash),
            )
            row = await cur.fetchone()
            await cur.execute(
                "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (new_user_id, "CLIENT_OWNER"),
            )
            client_id = await _create_core_client(
                user_id=str(new_user_id),
                email=payload.email,
                full_name=payload.full_name,
            )
            await cur.execute(
                "INSERT INTO user_clients (user_id, client_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (new_user_id, client_id),
            )
            await conn.commit()
        except HTTPException:
            await conn.rollback()
            raise
        except Exception:
            await conn.rollback()
            logger.exception("Failed to register user")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="signup_failed")

    user = User.from_row(row)
    roles = await _get_roles_for_user(str(new_user_id))
    expires_in = settings.access_token_expires_min * 60
    issuer, audience = _portal_token_config("client")
    tenant_token_version = await _get_tenant_token_version(user.tenant_id)
    try:
        token = create_access_token(
            user.email,
            roles=roles,
            subject_type="client_user",
            client_id=client_id,
            user_id=str(new_user_id),
            portal="client",
            issuer=issuer,
            audience=audience,
            tenant_id=user.tenant_id,
            token_version=user.token_version,
            tenant_token_version=tenant_token_version,
        )
    except InvalidRSAKeyError:
        logger.error("RSA keys unavailable during signup", extra={"email": payload.email})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rsa_keys_unavailable")
    return SignupResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        subject_type="client_user",
        client_id=client_id,
        roles=roles,
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: Request, payload: RegisterRequest) -> SignupResponse:
    return await register(request, payload)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if settings.force_sso and settings.disable_password_login:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_login_disabled")

    login_email = payload.email.strip().lower() if payload.email else None
    login_username = payload.username.strip().lower() if payload.username else None
    login_identifier = login_email or login_username or ""
    portal = _resolve_login_portal(request, payload)
    tenant = await _resolve_tenant(request=request, tenant_code=request.query_params.get("tenant"))
    if tenant["sso_enforced"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_login_disabled")

    subject_type = "user"
    user_email = login_email or ""
    client_id = None
    org_id = None

    logger.info(
        "login attempt: login=%s", login_identifier
    )

    try:
        user = await _get_user_from_db(email=login_email, username=login_username)
    except Exception:
        logger.exception(
            "Failed to fetch user during login", extra={"login": login_identifier}
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal_error")

    logger.info(
        "login attempt: login=%s, user_found=%s",
        login_identifier,
        bool(user),
    )

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.tenant_id and str(user.tenant_id) != str(tenant["id"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")
    if user.status == "blocked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_blocked")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    roles = await _get_roles_for_user(user.id)
    user_email = user.email

    expires_in = settings.access_token_expires_min * 60
    issuer, audience = _portal_token_config(portal)
    if portal == "client":
        subject_type = "client_user"
        client_id = await _get_client_id_for_user(str(user.id))
        if not client_id and _is_dev_env():
            client_id = settings.demo_client_uuid
            org_id = settings.demo_org_id
    if portal == "partner":
        subject_type = "partner_user"
        if org_id is None and _is_dev_env():
            org_id = settings.demo_org_id
    tenant_token_version = await _get_tenant_token_version(user.tenant_id)
    try:
        token = create_access_token(
            user_email,
            roles=roles,
            subject_type=subject_type,
            client_id=client_id,
            user_id=str(user.id),
            org_id=org_id,
            portal=portal,
            issuer=issuer,
            audience=audience,
            tenant_id=user.tenant_id,
            token_version=user.token_version,
            tenant_token_version=tenant_token_version,
        )
    except InvalidRSAKeyError:
        logger.error("RSA keys unavailable during login", extra={"login": login_identifier})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rsa_keys_unavailable")

    refresh_token, refresh_jti, refresh_exp = _create_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        device_key=_device_key(request),
    )
    try:
        await _persist_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            refresh_token=refresh_token,
            expires_at=refresh_exp,
            device_key=_device_key(request),
        )
    except Exception:
        logger.warning("refresh token persistence skipped")
    logger.info("login success", extra={"event_type": "login_success", "tenant_id": user.tenant_id, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        email=user_email,
        subject_type=subject_type,
        client_id=client_id,
        roles=roles,
    )


@router.get("/oauth/start")
async def oauth_start(request: Request, provider: str, portal: str, redirect_url: str | None = None, tenant: str | None = None) -> RedirectResponse:
    _oidc_enabled_or_503()
    resolved_portal = _resolve_portal(portal)
    if not resolved_portal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_portal")

    resolved_tenant = await _resolve_tenant(request=request, tenant_code=tenant)
    provider_cfg = await oidc_client.resolve_provider(provider, tenant_id=str(resolved_tenant["id"]))
    redirect = await oidc_client.build_start_redirect(
        provider=provider_cfg,
        portal=resolved_portal,
        redirect_url=redirect_url,
        tenant_id=str(resolved_tenant["id"]),
    )
    return RedirectResponse(url=redirect, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/oauth/callback", response_model=TokenResponse)
async def oauth_callback(request: Request, code: str, state: str) -> TokenResponse:
    _oidc_enabled_or_503()
    provider_name = oidc_client.provider_from_state(state)
    tenant = await _resolve_tenant(request=request, tenant_code=request.query_params.get("tenant"))
    provider_cfg = await oidc_client.resolve_provider(provider_name, tenant_id=str(tenant["id"]))
    result = await oidc_client.exchange_code_and_validate(provider=provider_cfg, code=code, state=state)
    claims = result["claims"]

    user = await _resolve_or_create_oauth_user(
        tenant_id=str(tenant["id"]),
        provider_id=provider_cfg.id,
        provider_name=provider_cfg.name,
        claims=claims,
    )
    if str(result.get("tenant_id") or "") != str(tenant["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_mismatch")
    roles = await oidc_client.map_roles(provider_cfg.id, claims)
    await _upsert_user_roles(user.id, roles)

    settings = get_settings()
    portal = _resolve_portal(result.get("portal")) or "client"
    issuer, audience = _portal_token_config(portal)
    subject_type = "user"
    client_id = None
    org_id = None
    if portal == "client":
        subject_type = "client_user"
        client_id = await _get_client_id_for_user(user.id)
        if not client_id:
            client_id = await _create_core_client(user_id=user.id, email=user.email, full_name=user.full_name)
            async with get_conn() as (conn, cur):
                await cur.execute(
                    "INSERT INTO user_clients (user_id, client_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user.id, client_id),
                )
                await conn.commit()
    elif portal == "partner":
        subject_type = "partner_user"
        if _is_dev_env():
            org_id = settings.demo_org_id

    tenant_token_version = await _get_tenant_token_version(user.tenant_id)
    token = create_access_token(
        user.id,
        roles=roles,
        subject_type=subject_type,
        client_id=client_id,
        user_id=user.id,
        org_id=org_id,
        portal=portal,
        issuer=issuer,
        audience=audience,
        email=user.email,
        tenant_id=user.tenant_id,
        token_version=user.token_version,
        tenant_token_version=tenant_token_version,
    )
    refresh_token, refresh_jti, refresh_exp = _create_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        device_key=_device_key(request),
    )
    try:
        await _persist_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            refresh_token=refresh_token,
            expires_at=refresh_exp,
            device_key=_device_key(request),
        )
    except Exception:
        logger.warning("refresh token persistence skipped")
    logger.info("sso login", extra={"event_type": "sso_login", "tenant_id": user.tenant_id, "user_id": user.id})
    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expires_min * 60,
        email=user.email,
        subject_type=subject_type,
        client_id=client_id,
        roles=roles,
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> VerifyResponse:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    portal = _resolve_portal(request.headers.get("X-Portal")) or _resolve_portal(request.query_params.get("portal")) or "client"
    issuer, audience = _portal_token_config(portal)
    payload = decode_access_token(credentials.credentials, issuer=issuer, audience=audience)
    token_portal = _resolve_portal(payload.get("portal")) or portal
    if token_portal != portal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong_portal")

    return VerifyResponse(valid=True, portal=portal, subject=str(payload.get("sub") or ""), user_id=payload.get("user_id"), roles=payload.get("roles") or [])


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: Request, payload: RefreshRequest) -> TokenResponse:
    token_payload = _decode_refresh_token(payload.refresh_token)
    token_hash = _hash_refresh_token(payload.refresh_token)
    device_key = _device_key(request)

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, user_id, tenant_id, expires_at, revoked, used_at, rotated_from, device_key
            FROM refresh_tokens
            WHERE token_hash=%s
            LIMIT 1
            """,
            (token_hash,),
        )
        row = await cur.fetchone()
        if not row:
            logger.info("refresh failed", extra={"event_type": "refresh_failed"})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")
        if row["revoked"] or row["used_at"] is not None or row["expires_at"] < datetime.now(tz=timezone.utc):
            await cur.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=%s AND tenant_id=%s", (row["user_id"], row["tenant_id"]))
            await conn.commit()
            logger.warning("refresh reuse", extra={"event_type": "refresh_reuse", "tenant_id": row["tenant_id"], "user_id": row["user_id"]})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh_reused")
        if row.get("device_key") and row["device_key"] != device_key:
            await cur.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE id=%s", (row["id"],))
            await conn.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device_mismatch")

        await cur.execute("UPDATE refresh_tokens SET revoked=TRUE, used_at=now() WHERE id=%s", (row["id"],))

        await cur.execute(
            "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at FROM users WHERE id=%s",
            (row["user_id"],),
        )
        user_row = await cur.fetchone()
        if not user_row:
            await conn.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
        user = User.from_row(user_row)
        if user.status == "blocked" or not user.is_active:
            await cur.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=%s AND tenant_id=%s", (row["user_id"], row["tenant_id"]))
            await conn.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_blocked")

        roles = await _get_roles_for_user(user.id)
        tenant_token_version = await _get_tenant_token_version(user.tenant_id)
        issuer, audience = _portal_token_config("client")
        access_token = create_access_token(
            user.email,
            roles=roles,
            subject_type="client_user",
            user_id=user.id,
            portal="client",
            issuer=issuer,
            audience=audience,
            email=user.email,
            tenant_id=user.tenant_id,
            token_version=user.token_version,
            tenant_token_version=tenant_token_version,
        )
        new_refresh, _new_jti, new_exp = _create_refresh_token(
            user_id=user.id,
            tenant_id=str(row["tenant_id"]),
            device_key=device_key,
            prev_jti=token_payload.get("jti"),
        )
        await cur.execute(
            """
            INSERT INTO refresh_tokens (user_id, tenant_id, token_hash, expires_at, rotated_from, device_key)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user.id, row["tenant_id"], _hash_refresh_token(new_refresh), new_exp, row["id"], device_key),
        )
        await conn.commit()

    logger.info("refresh rotation", extra={"event_type": "refresh_rotation", "tenant_id": user.tenant_id, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=get_settings().access_token_expires_min * 60,
        email=user.email,
        subject_type="client_user",
        roles=roles,
    )


@router.post("/admin/revoke-user")
async def revoke_user_tokens(payload: RevokeUserTokensRequest) -> dict:
    async with get_conn() as (conn, cur):
        await cur.execute("UPDATE users SET token_version=token_version+1 WHERE id=%s", (payload.user_id,))
        await cur.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=%s", (payload.user_id,))
        await conn.commit()
    return {"status": "ok"}


@router.post("/admin/revoke-tenant")
async def revoke_tenant_tokens(payload: RevokeTenantTokensRequest) -> dict:
    async with get_conn() as (conn, cur):
        await cur.execute("UPDATE tenants SET token_version=token_version+1 WHERE id=%s", (payload.tenant_id,))
        await cur.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE tenant_id=%s", (payload.tenant_id,))
        await conn.commit()
    return {"status": "ok"}


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

    email = payload.get("email") or subject
    roles = payload.get("roles") or []
    client_id = payload.get("client_id")
    subject_type = payload.get("subject_type", "user")
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    token_version = int(payload.get("token_version") or 1)
    tenant_token_version = int(payload.get("tenant_token_version") or 1)
    if user_id and tenant_id:
        async with get_conn() as (_conn, cur):
            await cur.execute("SELECT status, token_version FROM users WHERE id=%s", (user_id,))
            user_row = await cur.fetchone()
            await cur.execute("SELECT token_version FROM tenants WHERE id=%s", (tenant_id,))
            tenant_row = await cur.fetchone()
        if not user_row or str(user_row["status"]) == "blocked":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
        if int(user_row["token_version"]) != token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_revoked")
        if not tenant_row or int(tenant_row["token_version"]) != tenant_token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_revoked")
    return AuthMeResponse(
        email=email,
        roles=roles,
        subject=subject,
        subject_type=subject_type,
        client_id=client_id,
        portal=portal,
        user_id=user_id,
    )

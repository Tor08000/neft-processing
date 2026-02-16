from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.routes.auth import (
    _create_core_client,
    _create_refresh_token,
    _device_key,
    _get_client_id_for_user,
    _get_roles_for_user,
    _get_tenant_token_version,
    _is_dev_env,
    _persist_refresh_token,
    _portal_token_config,
)
from app.db import get_conn
from app.models import User
from app.security import create_access_token, hash_password
from app.services.oidc import oidc_service
from app.settings import get_settings

router = APIRouter(prefix="/v1/auth/sso", tags=["sso"])


@router.get("/idps")
async def list_idps(tenant_id: str, portal: str = "client") -> dict:
    idps = await oidc_service.list_idps(tenant_id)
    return {"tenant_id": tenant_id, "portal": portal, "idps": idps}


@router.get("/oidc/start")
async def oidc_start(tenant_id: str, provider_key: str, portal: str, redirect_uri: str) -> RedirectResponse:
    redirect = await oidc_service.build_start_redirect(
        tenant_id=tenant_id,
        provider_key=provider_key,
        portal=portal,
        redirect_uri=redirect_uri,
    )
    return RedirectResponse(url=redirect, status_code=status.HTTP_302_FOUND)


async def _resolve_or_create_identity_user(*, tenant_id: str, provider_key: str, provider_id: str, claims: dict) -> User:
    email = (claims.get("email") or "").strip().lower()
    subject = str(claims.get("sub") or "").strip()
    full_name = claims.get("name")
    if not subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="oidc_subject_required")

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT u.id, u.tenant_id, u.email, u.username, u.full_name, u.password_hash, u.is_active, u.status, u.token_version, u.created_at
            FROM user_identities ui
            JOIN users u ON u.id = ui.user_id
            WHERE ui.tenant_id=%s AND ui.provider_key=%s AND ui.external_sub=%s
            LIMIT 1
            """,
            (tenant_id, provider_key, subject),
        )
        row = await cur.fetchone()
        if row:
            return User.from_row(row)

        user = None
        if email:
            await cur.execute(
                """
                SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at
                FROM users
                WHERE tenant_id=%s AND lower(email)=lower(%s)
                LIMIT 1
                """,
                (tenant_id, email),
            )
            existing = await cur.fetchone()
            if existing:
                user = User.from_row(existing)

        if not user:
            user_id = str(uuid4())
            await cur.execute(
                """
                INSERT INTO users (id, tenant_id, email, full_name, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at
                """,
                (user_id, tenant_id, email or f"{subject}@sso.local", full_name, hash_password(uuid4().hex)),
            )
            user = User.from_row(await cur.fetchone())

        await cur.execute(
            """
            INSERT INTO user_identities (user_id, tenant_id, provider_key, external_sub, external_email, raw_claims)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (tenant_id, provider_key, external_sub)
            DO UPDATE SET external_email=EXCLUDED.external_email, raw_claims=EXCLUDED.raw_claims
            """,
            (user.id, tenant_id, provider_key, subject, email or None, "{}"),
        )
        await conn.commit()

    return user


@router.get("/oidc/callback")
async def oidc_callback(request: Request, code: str, state: str) -> dict:
    state_payload = oidc_service.decode_state(state)
    state_id = str(state_payload.get("sid") or "")
    if not state_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, tenant_id, provider_key, portal, redirect_uri, nonce, code_verifier, expires_at, consumed_at
            FROM sso_oidc_states
            WHERE id=%s
            LIMIT 1
            """,
            (state_id,),
        )
        row = await cur.fetchone()
        if not row or row["consumed_at"] is not None or row["expires_at"] < datetime.now(tz=timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")

        provider = await oidc_service.resolve_provider(row["tenant_id"], row["provider_key"])
        token_data = await oidc_service.exchange_code(
            provider=provider,
            code=code,
            redirect_uri=row["redirect_uri"],
            code_verifier=row["code_verifier"],
        )
        id_token = token_data.get("id_token")
        if not id_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_missing_id_token")

        claims = await oidc_service.validate_id_token(provider=provider, id_token=id_token, nonce=row["nonce"])
        user = await _resolve_or_create_identity_user(
            tenant_id=row["tenant_id"],
            provider_key=row["provider_key"],
            provider_id=provider.id,
            claims=claims,
        )
        await cur.execute("UPDATE sso_oidc_states SET consumed_at=now() WHERE id=%s", (state_id,))

        one_time_code = secrets.token_urlsafe(32)
        await cur.execute(
            """
            INSERT INTO sso_exchange_codes (code, user_id, tenant_id, portal, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                one_time_code,
                user.id,
                user.tenant_id,
                row["portal"],
                datetime.now(tz=timezone.utc) + timedelta(minutes=3),
            ),
        )
        await conn.commit()

    return {"code": one_time_code, "redirect_uri": row["redirect_uri"]}


@router.post("/exchange")
async def exchange_code(request: Request, payload: dict) -> dict:
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code_required")

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT code, user_id, tenant_id, portal, expires_at, consumed_at
            FROM sso_exchange_codes
            WHERE code=%s
            LIMIT 1
            """,
            (code,),
        )
        row = await cur.fetchone()
        if not row or row["consumed_at"] is not None or row["expires_at"] < datetime.now(tz=timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_code")

        await cur.execute(
            "SELECT id, tenant_id, email, username, full_name, password_hash, is_active, status, token_version, created_at FROM users WHERE id=%s",
            (row["user_id"],),
        )
        user_row = await cur.fetchone()
        if not user_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
        user = User.from_row(user_row)

        portal = row["portal"]
        issuer, audience = _portal_token_config(portal)
        subject_type = "user"
        client_id = None
        org_id = None
        if portal == "client":
            subject_type = "client_user"
            client_id = await _get_client_id_for_user(user.id)
            if not client_id:
                client_id = await _create_core_client(user_id=user.id, email=user.email, full_name=user.full_name)
                await cur.execute(
                    "INSERT INTO user_clients (user_id, client_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user.id, client_id),
                )
        elif portal == "partner" and _is_dev_env():
            org_id = get_settings().demo_org_id
            subject_type = "partner_user"

        roles = await _get_roles_for_user(user.id)
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

        refresh_token, _, refresh_exp = _create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            device_key=_device_key(request),
        )
        await _persist_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            refresh_token=refresh_token,
            expires_at=refresh_exp,
            device_key=_device_key(request),
        )
        await cur.execute("UPDATE sso_exchange_codes SET consumed_at=now() WHERE code=%s", (code,))
        await conn.commit()

    return {"access_token": token, "refresh_token": refresh_token, "token_type": "bearer"}

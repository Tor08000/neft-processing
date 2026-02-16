from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.db import get_conn
from app.security import decode_access_token, security_scheme

router = APIRouter(prefix="/v1/auth/admin/sso/idps", tags=["admin-sso"])


async def _require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    payload = decode_access_token(credentials.credentials)
    roles = payload.get("roles") or []
    if "ADMIN" not in roles and "PLATFORM_ADMIN" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return payload


@router.get("")
async def list_idps(tenant_id: str, _admin=Depends(_require_admin)) -> list[dict[str, Any]]:
    async with get_conn() as (_conn, cur):
        await cur.execute(
            """
            SELECT id, tenant_id, provider_key, display_name, issuer_url, client_id, scopes, enabled, created_at, updated_at
            FROM sso_idp_configs
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )
        rows = await cur.fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_idp(payload: dict, _admin=Depends(_require_admin)) -> dict:
    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            INSERT INTO sso_idp_configs (
                tenant_id, provider_key, display_name, issuer_url, client_id, client_secret,
                authorization_endpoint, token_endpoint, userinfo_endpoint, jwks_uri,
                scopes, claim_email, claim_sub, claim_name, allowed_domains, enabled
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                payload["tenant_id"],
                payload["provider_key"],
                payload.get("display_name") or payload["provider_key"],
                payload["issuer_url"],
                payload["client_id"],
                payload.get("client_secret"),
                payload.get("authorization_endpoint"),
                payload.get("token_endpoint"),
                payload.get("userinfo_endpoint"),
                payload.get("jwks_uri"),
                payload.get("scopes") or "openid profile email",
                payload.get("claim_email") or "email",
                payload.get("claim_sub") or "sub",
                payload.get("claim_name") or "name",
                payload.get("allowed_domains"),
                bool(payload.get("enabled", True)),
            ),
        )
        row = await cur.fetchone()
        await conn.commit()
    return {"id": row["id"]}


@router.patch("/{idp_id}")
async def patch_idp(idp_id: str, payload: dict, _admin=Depends(_require_admin)) -> dict:
    allowed_fields = {
        "display_name",
        "issuer_url",
        "client_id",
        "client_secret",
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
        "scopes",
        "claim_email",
        "claim_sub",
        "claim_name",
        "allowed_domains",
        "enabled",
    }
    updates = []
    values: list[Any] = []
    for key, value in payload.items():
        if key in allowed_fields:
            updates.append(f"{key}=%s")
            values.append(value)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_patch")

    async with get_conn() as (conn, cur):
        await cur.execute(
            f"UPDATE sso_idp_configs SET {', '.join(updates)}, updated_at=now() WHERE id=%s",
            (*values, idp_id),
        )
        await conn.commit()
    return {"status": "ok"}


@router.delete("/{idp_id}")
async def delete_idp(idp_id: str, _admin=Depends(_require_admin)) -> None:
    async with get_conn() as (conn, cur):
        await cur.execute("DELETE FROM sso_idp_configs WHERE id=%s", (idp_id,))
        await conn.commit()

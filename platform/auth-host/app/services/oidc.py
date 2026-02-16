from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import jwt

from app.db import get_conn
from app.settings import get_settings


@dataclass
class SSOIdPConfig:
    id: str
    tenant_id: str
    provider_key: str
    display_name: str
    issuer_url: str
    client_id: str
    client_secret: str | None
    authorization_endpoint: str | None
    token_endpoint: str | None
    userinfo_endpoint: str | None
    jwks_uri: str | None
    scopes: str
    claim_email: str
    claim_sub: str
    claim_name: str
    allowed_domains: list[str] | None
    enabled: bool


class OIDCService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._timeout = httpx.Timeout(10.0)

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return verifier, challenge

    def encode_state(self, payload: dict[str, Any], ttl_minutes: int | None = None) -> str:
        ttl = self.settings.oidc_state_ttl_minutes if ttl_minutes is None else ttl_minutes
        now = datetime.now(tz=timezone.utc)
        state_payload = {
            **payload,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=ttl)).timestamp()),
        }
        return jwt.encode(state_payload, self.settings.oidc_state_secret, algorithm="HS256")

    def decode_state(self, state: str) -> dict[str, Any]:
        try:
            return jwt.decode(state, self.settings.oidc_state_secret, algorithms=["HS256"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state") from exc

    async def list_idps(self, tenant_id: str) -> list[dict[str, Any]]:
        async with get_conn() as (_conn, cur):
            await cur.execute(
                """
                SELECT provider_key, display_name, issuer_url, enabled
                FROM sso_idp_configs
                WHERE tenant_id=%s AND enabled=TRUE
                ORDER BY display_name
                """,
                (tenant_id,),
            )
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def resolve_provider(self, tenant_id: str, provider_key: str) -> SSOIdPConfig:
        async with get_conn() as (_conn, cur):
            await cur.execute(
                """
                SELECT id, tenant_id, provider_key, display_name, issuer_url, client_id, client_secret,
                       authorization_endpoint, token_endpoint, userinfo_endpoint, jwks_uri,
                       scopes, claim_email, claim_sub, claim_name, allowed_domains, enabled
                FROM sso_idp_configs
                WHERE tenant_id=%s AND provider_key=%s AND enabled=TRUE
                LIMIT 1
                """,
                (tenant_id, provider_key),
            )
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sso_provider_not_found")
        return SSOIdPConfig(**dict(row))

    async def _discovery(self, provider: SSOIdPConfig) -> dict[str, Any]:
        if provider.authorization_endpoint and provider.token_endpoint and provider.jwks_uri:
            return {
                "issuer": provider.issuer_url,
                "authorization_endpoint": provider.authorization_endpoint,
                "token_endpoint": provider.token_endpoint,
                "jwks_uri": provider.jwks_uri,
            }

        url = f"{provider.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        return data

    async def build_start_redirect(
        self,
        *,
        tenant_id: str,
        provider_key: str,
        portal: str,
        redirect_uri: str,
    ) -> str:
        provider = await self.resolve_provider(tenant_id, provider_key)
        discovery = await self._discovery(provider)
        nonce = secrets.token_urlsafe(24)
        code_verifier, code_challenge = self.generate_pkce_pair()
        state_id = secrets.token_urlsafe(24)

        state = self.encode_state(
            {
                "sid": state_id,
                "tenant_id": tenant_id,
                "provider_key": provider_key,
                "portal": portal,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
                "code_verifier": code_verifier,
            }
        )
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=self.settings.oidc_state_ttl_minutes)

        async with get_conn() as (conn, cur):
            await cur.execute(
                """
                INSERT INTO sso_oidc_states (id, tenant_id, provider_key, portal, redirect_uri, nonce, code_verifier, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (state_id, tenant_id, provider_key, portal, redirect_uri, nonce, code_verifier, expires_at),
            )
            await conn.commit()

        params = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "scope": provider.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{discovery['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(self, *, provider: SSOIdPConfig, code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
        discovery = await self._discovery(provider)
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id,
            "code_verifier": code_verifier,
        }
        if provider.client_secret:
            payload["client_secret"] = provider.client_secret
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(discovery["token_endpoint"], data=payload)
            response.raise_for_status()
            return response.json()

    async def validate_id_token(self, *, provider: SSOIdPConfig, id_token: str, nonce: str) -> dict[str, Any]:
        discovery = await self._discovery(provider)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(discovery["jwks_uri"])
            response.raise_for_status()
            jwks = response.json()

        try:
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=provider.client_id,
                issuer=provider.issuer_url,
                options={"verify_at_hash": False},
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_invalid_id_token") from exc

        if claims.get("nonce") != nonce:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_invalid_nonce")
        return claims


oidc_service = OIDCService()

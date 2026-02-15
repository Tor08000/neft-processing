from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


@dataclass
class OIDCProviderConfig:
    id: str | None
    name: str
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    enabled: bool


@dataclass
class OIDCDiscovery:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


class OIDCClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._timeout = httpx.Timeout(10.0)
        self._discovery_cache: dict[str, tuple[OIDCDiscovery, datetime]] = {}
        self._jwks_cache: dict[str, tuple[dict[str, Any], datetime]] = {}

    async def resolve_provider(self, provider_name: str, *, tenant_id: str | None = None) -> OIDCProviderConfig:
        provider = await self._provider_from_db(provider_name, tenant_id=tenant_id)
        if provider:
            return provider
        provider = self._provider_from_env(provider_name)
        if provider:
            return provider
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="oidc_provider_not_found")

    async def _provider_from_db(self, provider_name: str, *, tenant_id: str | None = None) -> OIDCProviderConfig | None:
        try:
            async with get_conn() as (_conn, cur):
                await cur.execute(
                """
                SELECT id, name, issuer, client_id, client_secret, redirect_uri, scopes, enabled, tenant_id
                FROM oidc_providers
                WHERE lower(name)=lower(%s) AND (%s::uuid IS NULL OR tenant_id=%s::uuid)
                LIMIT 1
                """,
                (provider_name, tenant_id, tenant_id),
            )
                row = await cur.fetchone()
        except Exception:
            return None
        if not row:
            return None
        return OIDCProviderConfig(
            id=str(row["id"]),
            name=row["name"],
            issuer=row["issuer"],
            client_id=row["client_id"],
            client_secret=row["client_secret"],
            redirect_uri=row["redirect_uri"],
            scopes=row["scopes"] or "openid email profile",
            enabled=bool(row["enabled"]),
        )

    def _provider_from_env(self, provider_name: str) -> OIDCProviderConfig | None:
        if not self.settings.oidc_enabled:
            return None
        if self.settings.oidc_provider_name.lower() != provider_name.lower():
            return None
        return OIDCProviderConfig(
            id=None,
            name=self.settings.oidc_provider_name,
            issuer=self.settings.oidc_issuer,
            client_id=self.settings.oidc_client_id,
            client_secret=self.settings.oidc_client_secret,
            redirect_uri=self.settings.oidc_redirect_uri,
            scopes=self.settings.oidc_scopes,
            enabled=True,
        )

    async def get_discovery(self, provider: OIDCProviderConfig) -> OIDCDiscovery:
        cached = self._discovery_cache.get(provider.issuer)
        if cached and cached[1] > datetime.now(tz=timezone.utc):
            return cached[0]

        url = f"{provider.issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        discovery = OIDCDiscovery(
            issuer=data.get("issuer", ""),
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            jwks_uri=data["jwks_uri"],
        )
        if discovery.issuer.rstrip("/") != provider.issuer.rstrip("/"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="oidc_invalid_issuer")

        self._discovery_cache[provider.issuer] = (
            discovery,
            datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        )
        return discovery

    async def build_start_redirect(
        self,
        *,
        provider: OIDCProviderConfig,
        portal: str,
        redirect_url: str | None,
        tenant_id: str,
    ) -> str:
        if not provider.enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="oidc_provider_disabled")

        discovery = await self.get_discovery(provider)
        nonce = secrets.token_urlsafe(24)
        state_payload = {
            "sid": secrets.token_urlsafe(24),
            "provider": provider.name,
            "provider_id": provider.id,
            "tenant_id": tenant_id,
            "portal": portal,
            "nonce": nonce,
            "redirect_url": redirect_url,
            "iat": int(datetime.now(tz=timezone.utc).timestamp()),
        }
        state = jwt.encode(state_payload, self.settings.oidc_state_secret, algorithm="HS256")

        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=self.settings.oidc_state_ttl_minutes)
        async with get_conn() as (conn, cur):
            await cur.execute(
                """
                INSERT INTO oauth_states (state_id, provider_name, portal, nonce, redirect_url, expires_at, tenant_id, provider_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    state_payload["sid"],
                    provider.name,
                    portal,
                    nonce,
                    redirect_url,
                    expires_at,
                    tenant_id,
                    provider.id,
                ),
            )
            await conn.commit()

        params = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": provider.redirect_uri,
            "scope": provider.scopes,
            "state": state,
            "nonce": nonce,
        }
        return f"{discovery.authorization_endpoint}?{urlencode(params)}"

    def provider_from_state(self, state: str) -> str:
        try:
            payload = jwt.decode(state, self.settings.oidc_state_secret, algorithms=["HS256"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state") from exc
        provider = str(payload.get("provider") or "").strip()
        if not provider:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
        return provider

    async def exchange_code_and_validate(
        self,
        *,
        provider: OIDCProviderConfig,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        discovery = await self.get_discovery(provider)
        try:
            state_payload = jwt.decode(state, self.settings.oidc_state_secret, algorithms=["HS256"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state") from exc

        state_id = state_payload.get("sid")
        if not state_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")

        async with get_conn() as (conn, cur):
            await cur.execute(
                """
                SELECT provider_name, portal, nonce, redirect_url, expires_at, consumed_at, tenant_id, provider_id
                FROM oauth_states
                WHERE state_id=%s
                LIMIT 1
                """,
                (state_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
            if row["consumed_at"] is not None or row["expires_at"] < datetime.now(tz=timezone.utc):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
            if row["provider_name"].lower() != provider.name.lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
            if str(row.get("provider_id") or "") and provider.id and str(row["provider_id"]) != str(provider.id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
            if state_payload.get("tenant_id") and str(row.get("tenant_id") or "") != str(state_payload.get("tenant_id")):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
            await cur.execute(
                "UPDATE oauth_states SET consumed_at=now() WHERE state_id=%s",
                (state_id,),
            )
            await conn.commit()

        token_payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": provider.redirect_uri,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            token_response = await client.post(discovery.token_endpoint, data=token_payload)
            token_response.raise_for_status()
            token_data = token_response.json()

        id_token = token_data.get("id_token")
        if not id_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_missing_id_token")

        header = jwt.get_unverified_header(id_token)
        if header.get("alg") != "RS256":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_invalid_alg")

        claims = await self._decode_with_jwks(
            id_token,
            jwks_uri=discovery.jwks_uri,
            issuer=provider.issuer,
            audience=provider.client_id,
        )
        if claims.get("nonce") != state_payload.get("nonce"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_invalid_nonce")

        return {
            "claims": claims,
            "portal": state_payload.get("portal"),
            "redirect_url": state_payload.get("redirect_url"),
            "tenant_id": state_payload.get("tenant_id"),
        }

    async def _decode_with_jwks(self, token: str, *, jwks_uri: str, issuer: str, audience: str) -> dict[str, Any]:
        jwks = await self._get_jwks(jwks_uri)
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                options={"verify_at_hash": False},
            )
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="oidc_invalid_id_token") from exc

    async def _get_jwks(self, jwks_uri: str) -> dict[str, Any]:
        cached = self._jwks_cache.get(jwks_uri)
        if cached and cached[1] > datetime.now(tz=timezone.utc):
            return cached[0]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(jwks_uri)
            response.raise_for_status()
            jwks = response.json()
        self._jwks_cache[jwks_uri] = (jwks, datetime.now(tz=timezone.utc) + timedelta(minutes=30))
        return jwks

    async def map_roles(self, provider_id: str | None, claims: dict[str, Any]) -> list[str]:
        external_roles = self._extract_external_roles(claims)
        if not external_roles:
            return [self.settings.oidc_default_role]

        mapped: list[str] = []
        try:
            async with get_conn() as (_conn, cur):
                for role in external_roles:
                    if provider_id:
                        await cur.execute(
                            """
                            SELECT internal_role FROM oidc_role_mappings
                            WHERE provider_id=%s AND external_role=%s
                            LIMIT 1
                            """,
                            (provider_id, role),
                        )
                        row = await cur.fetchone()
                        if row:
                            mapped.append(row["internal_role"])
                            continue
                    await cur.execute(
                        """
                        SELECT internal_role FROM oidc_role_mappings
                        WHERE provider_id IS NULL AND external_role=%s
                        LIMIT 1
                        """,
                        (role,),
                    )
                    row = await cur.fetchone()
                    if row:
                        mapped.append(row["internal_role"])
        except Exception:
            return [self.settings.oidc_default_role]

        unique = sorted({r for r in mapped if r})
        return unique or [self.settings.oidc_default_role]

    @staticmethod
    def _extract_external_roles(claims: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for key in ("groups", "roles"):
            payload = claims.get(key)
            if isinstance(payload, list):
                values.extend(str(item) for item in payload)
        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict) and isinstance(realm_access.get("roles"), list):
            values.extend(str(item) for item in realm_access["roles"])
        return sorted({v.strip() for v in values if str(v).strip()})

    async def fail_fast_validate_enabled_providers(self) -> None:
        if not self.settings.oidc_enabled:
            logger.info("OIDC: disabled")
            return

        providers: list[OIDCProviderConfig] = []
        env_provider = self._provider_from_env(self.settings.oidc_provider_name)
        if env_provider:
            providers.append(env_provider)

        try:
            async with get_conn() as (_conn, cur):
                await cur.execute(
                    """
                    SELECT id, name, issuer, client_id, client_secret, redirect_uri, scopes, enabled
                    FROM oidc_providers
                    WHERE enabled=TRUE
                    """
                )
                rows = await cur.fetchall()
                for row in rows:
                    providers.append(
                        OIDCProviderConfig(
                            id=str(row["id"]),
                            name=row["name"],
                            issuer=row["issuer"],
                            client_id=row["client_id"],
                            client_secret=row["client_secret"],
                            redirect_uri=row["redirect_uri"],
                            scopes=row["scopes"] or "openid email profile",
                            enabled=True,
                        )
                    )
        except Exception:
            pass

        if not providers:
            raise SystemExit("OIDC enabled but no providers configured")

        for provider in providers:
            logger.info("OIDC: enabled provider=%s issuer=%s", provider.name, provider.issuer)
            try:
                await self.get_discovery(provider)
            except Exception as exc:
                raise SystemExit(f"OIDC discovery failed for {provider.name}: {exc}") from exc


oidc_client = OIDCClient()

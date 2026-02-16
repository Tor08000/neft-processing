from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.request import urlopen

from fastapi import Header, HTTPException
from jose import jwt


@dataclass
class Actor:
    actor_type: str
    actor_id: str | None
    actor_email: str | None


@dataclass
class AuthContext:
    tenant_id: str
    actor: Actor
    roles: set[str]


CRM_AUDIENCE = {item.strip() for item in os.getenv("CRM_AUTH_AUDIENCE", "neft-admin,neft-partner").split(",") if item.strip()}
CRM_INTERNAL_TOKEN = os.getenv("CRM_INTERNAL_TOKEN")
CRM_AUTH_DISABLED_FOR_TESTS = os.getenv("CRM_AUTH_DISABLED_FOR_TESTS", "0") == "1"
JWKS_URL = os.getenv("CRM_JWKS_URL")
JWT_ALGORITHMS = ["RS256", "HS256"]
JWT_SECRET = os.getenv("CRM_JWT_SECRET")


def _get_unverified_or_verify(token: str) -> dict:
    if JWT_SECRET:
        return jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGORITHMS, options={"verify_aud": False})
    if JWKS_URL:
        with urlopen(JWKS_URL, timeout=5) as response:  # noqa: S310
            jwks = json.loads(response.read().decode("utf-8"))
        header = jwt.get_unverified_header(token)
        key = next((item for item in jwks.get("keys", []) if item.get("kid") == header.get("kid")), None)
        if not key:
            raise HTTPException(status_code=401, detail="Unknown token kid")
        return jwt.decode(token, key, algorithms=["RS256"], options={"verify_aud": False})
    return jwt.get_unverified_claims(token)


def get_auth_context(
    authorization: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
) -> AuthContext:
    if CRM_AUTH_DISABLED_FOR_TESTS:
        return AuthContext(
            tenant_id=x_tenant_id or "test-tenant",
            actor=Actor(actor_type="ADMIN", actor_id="test-user", actor_email="test@example.com"),
            roles={"admin"},
        )

    if authorization and authorization.lower().startswith("bearer "):
        claims = _get_unverified_or_verify(authorization.split(" ", 1)[1])
        aud = claims.get("aud")
        aud_values = {aud} if isinstance(aud, str) else set(aud or [])
        if not aud_values.intersection(CRM_AUDIENCE):
            raise HTTPException(status_code=403, detail="Token audience is not allowed")
        tenant_id = str(claims.get("tenant_id") or claims.get("client_id") or "")
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Missing tenant_id/client_id in token")
        actor_id = str(claims.get("sub") or "") or None
        email = claims.get("email")
        actor_type = "PARTNER" if "neft-partner" in aud_values else "ADMIN"
        roles = claims.get("roles") or []
        roles_set = {str(item) for item in (roles if isinstance(roles, list) else [roles])}
        return AuthContext(tenant_id=tenant_id, actor=Actor(actor_type=actor_type, actor_id=actor_id, actor_email=email), roles=roles_set)

    if CRM_INTERNAL_TOKEN and x_internal_token and x_internal_token == CRM_INTERNAL_TOKEN and x_tenant_id:
        return AuthContext(
            tenant_id=x_tenant_id,
            actor=Actor(actor_type="SYSTEM", actor_id=None, actor_email=None),
            roles={"system"},
        )

    raise HTTPException(status_code=401, detail="Unauthorized")

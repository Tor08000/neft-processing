from __future__ import annotations

import os
import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwk, jwt

PUBLIC_KEY_URL = os.getenv(
    "ADMIN_PUBLIC_KEY_URL",
    os.getenv("CLIENT_PUBLIC_KEY_URL", "http://auth-host:8000/api/v1/auth/public-key"),
)
PUBLIC_KEY_CACHE_TTL = 300
EXPECTED_ISSUER = os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))
EXPECTED_AUDIENCE = os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-admin"))

ADMIN_ROLES = {
    role.strip()
    for role in os.getenv("ADMIN_ROLES", os.getenv("NEFT_ADMIN_ROLES", "ADMIN")).split(",")
    if role.strip()
}
if not ADMIN_ROLES:
    ADMIN_ROLES = {"ADMIN"}

_cached_public_key: Optional[str] = None
_public_key_cached_at: float = 0.0


def get_public_key(force_refresh: bool = False) -> str:
    global _cached_public_key, _public_key_cached_at

    now = time.time()
    if not force_refresh and _cached_public_key and now - _public_key_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_public_key

    fallback_key = os.getenv("ADMIN_PUBLIC_KEY")

    if fallback_key and not force_refresh and not _cached_public_key:
        _cached_public_key = fallback_key
        _public_key_cached_at = now
        return fallback_key

    try:
        response = requests.get(PUBLIC_KEY_URL, timeout=5)
        response.raise_for_status()
        _cached_public_key = response.text
        _public_key_cached_at = now
        return _cached_public_key
    except requests.RequestException as exc:  # pragma: no cover - network errors
        if fallback_key:
            _cached_public_key = fallback_key
            _public_key_cached_at = now
            return fallback_key
        raise HTTPException(status_code=503, detail="Unable to fetch public key") from exc


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


def verify_admin_token(token: str = Depends(_get_bearer_token)) -> dict:
    public_key = get_public_key()

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=EXPECTED_ISSUER,
        )
    except (JWTError, jwk.JWKError, ValueError):
        public_key = get_public_key(force_refresh=True)
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=EXPECTED_AUDIENCE,
                issuer=EXPECTED_ISSUER,
            )
        except (JWTError, jwk.JWKError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid token")

    admin_roles = set()

    role = payload.get("role")
    if role:
        admin_roles.add(role)

    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    admin_roles.update(roles)

    normalized_roles = {str(item).upper() for item in admin_roles}
    required = {role.upper() for role in ADMIN_ROLES}

    if not normalized_roles.intersection(required):
        raise HTTPException(status_code=403, detail="Forbidden")

    return payload


def require_admin(token: dict = Depends(verify_admin_token)) -> dict:
    return token

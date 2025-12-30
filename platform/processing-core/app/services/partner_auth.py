from __future__ import annotations

import os
import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwk, jwt


PUBLIC_KEY_URL = os.getenv(
    "PARTNER_PUBLIC_KEY_URL",
    os.getenv("ADMIN_PUBLIC_KEY_URL", "http://auth-host:8000/api/v1/auth/public-key"),
)
PUBLIC_KEY_CACHE_TTL = 300
EXPECTED_ISSUER = os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))
EXPECTED_AUDIENCE = os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-admin"))

_cached_public_key: Optional[str] = None
_public_key_cached_at: float = 0.0


def get_public_key(force_refresh: bool = False) -> str:
    global _cached_public_key, _public_key_cached_at

    now = time.time()
    if not force_refresh and _cached_public_key and now - _public_key_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_public_key

    fallback_key = os.getenv("PARTNER_PUBLIC_KEY") or os.getenv("ADMIN_PUBLIC_KEY")
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


def verify_partner_token(token: str = Depends(_get_bearer_token)) -> dict:
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

    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = payload.get("role")
    if role:
        roles.append(role)

    subject_type = payload.get("subject_type")
    has_partner_role = any(str(item).startswith("PARTNER_") for item in roles)
    if not has_partner_role and subject_type != "partner_user":
        raise HTTPException(status_code=403, detail="Forbidden")

    partner_id = payload.get("partner_id")
    if not partner_id:
        raise HTTPException(status_code=403, detail="Missing partner context")

    payload["user_id"] = payload.get("sub")
    payload["partner_id"] = partner_id
    return payload


def require_partner_user(token: dict = Depends(verify_partner_token)) -> dict:
    return token


__all__ = ["require_partner_user", "verify_partner_token"]

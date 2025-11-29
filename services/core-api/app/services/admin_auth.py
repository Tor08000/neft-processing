from __future__ import annotations

import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

PUBLIC_KEY_URL = "http://auth-host:8000/api/v1/auth/public-key"
PUBLIC_KEY_CACHE_TTL = 300
EXPECTED_ISSUER = "neft-auth"
EXPECTED_AUDIENCE = "neft-admin"

_cached_public_key: Optional[str] = None
_public_key_cached_at: float = 0.0


def get_public_key() -> str:
    global _cached_public_key, _public_key_cached_at

    now = time.time()
    if _cached_public_key and now - _public_key_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_public_key

    try:
        response = requests.get(PUBLIC_KEY_URL, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=503, detail="Unable to fetch public key") from exc

    _cached_public_key = response.text
    _public_key_cached_at = now
    return _cached_public_key


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
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    roles = payload.get("roles") or []
    if "ADMIN" not in roles:
        raise HTTPException(status_code=403, detail="Forbidden")

    return payload


def require_admin(token: dict = Depends(verify_admin_token)) -> dict:
    return token

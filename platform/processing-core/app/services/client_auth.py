from __future__ import annotations

import os
import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwk, jwt

PUBLIC_KEY_URL = os.getenv(
    "CLIENT_PUBLIC_KEY_URL",
    os.getenv("ADMIN_PUBLIC_KEY_URL", "http://auth-host:8000/api/v1/auth/public-key"),
)
PUBLIC_KEY_CACHE_TTL = 300
EXPECTED_ISSUER = os.getenv(
    "NEFT_CLIENT_ISSUER",
    os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-client")),
)
EXPECTED_AUDIENCE = os.getenv(
    "NEFT_CLIENT_AUDIENCE",
    os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-client")),
)

ALLOWED_CLIENT_ROLES = {
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_OWNER",
    "CLIENT_USER",
}

_cached_public_key: Optional[str] = None
_public_key_cached_at: float = 0.0


def get_public_key(force_refresh: bool = False) -> str:
    global _cached_public_key, _public_key_cached_at

    now = time.time()
    if not force_refresh and _cached_public_key and now - _public_key_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_public_key

    fallback_key = os.getenv("CLIENT_PUBLIC_KEY") or os.getenv("ADMIN_PUBLIC_KEY")
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


def verify_client_token(token: str = Depends(_get_bearer_token)) -> dict:
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
    role = payload.get("role") or next((r for r in roles if r in ALLOWED_CLIENT_ROLES), None)
    subject_type = payload.get("subject_type")
    if role not in ALLOWED_CLIENT_ROLES and subject_type != "client_user":
        raise HTTPException(status_code=403, detail="Forbidden")

    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")

    payload["user_id"] = payload.get("sub")
    if role:
        payload["role"] = role
    payload["client_id"] = client_id
    return payload


def verify_onboarding_token(token: str = Depends(_get_bearer_token)) -> dict:
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
    role = payload.get("role") or next((r for r in roles if r in ALLOWED_CLIENT_ROLES), None)
    subject_type = payload.get("subject_type")
    if role not in ALLOWED_CLIENT_ROLES and subject_type != "client_user":
        raise HTTPException(status_code=403, detail="Forbidden")

    payload["user_id"] = payload.get("user_id") or payload.get("sub")
    if role:
        payload["role"] = role
    return payload


def require_client_user(token: dict = Depends(verify_client_token)) -> dict:
    return token


def require_onboarding_user(token: dict = Depends(verify_onboarding_token)) -> dict:
    return token

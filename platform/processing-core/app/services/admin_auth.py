from __future__ import annotations

import os
import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwk, jwt
from neft_shared.logging_setup import get_logger

PUBLIC_KEY_URL = os.getenv(
    "ADMIN_PUBLIC_KEY_URL",
    os.getenv("CLIENT_PUBLIC_KEY_URL", "http://auth-host:8000/api/v1/auth/public-key"),
)
JWKS_URL = os.getenv(
    "ADMIN_JWKS_URL",
    os.getenv("AUTH_JWKS_URL", "http://auth-host:8000/.well-known/jwks.json"),
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
_cached_jwks: Optional[dict] = None
_jwks_cached_at: float = 0.0
_logger = get_logger(__name__)


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
        _logger.warning("admin_auth.public_key.fetch_failed", extra={"error": str(exc)})
        if fallback_key:
            _cached_public_key = fallback_key
            _public_key_cached_at = now
            return fallback_key
        raise HTTPException(status_code=503, detail="Unable to fetch public key") from exc


def _fetch_jwks(force_refresh: bool = False) -> dict:
    global _cached_jwks, _jwks_cached_at

    now = time.time()
    if not force_refresh and _cached_jwks and now - _jwks_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_jwks

    try:
        response = requests.get(JWKS_URL, timeout=5)
        _logger.info(
            "admin_auth.jwks.refresh",
            extra={"url": JWKS_URL, "status_code": response.status_code},
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        _logger.warning(
            "admin_auth.jwks.refresh_failed",
            extra={"url": JWKS_URL, "error": str(exc)},
        )
        if _cached_jwks:
            return _cached_jwks
        raise HTTPException(status_code=503, detail="Unable to fetch JWKS") from exc
    except ValueError as exc:
        _logger.warning(
            "admin_auth.jwks.invalid_payload",
            extra={"url": JWKS_URL, "error": str(exc)},
        )
        if _cached_jwks:
            return _cached_jwks
        raise HTTPException(status_code=503, detail="Unable to parse JWKS") from exc

    if not isinstance(payload, dict) or "keys" not in payload:
        _logger.warning(
            "admin_auth.jwks.invalid_payload",
            extra={"url": JWKS_URL, "detail": "missing_keys"},
        )
        if _cached_jwks:
            return _cached_jwks
        raise HTTPException(status_code=503, detail="Invalid JWKS payload")

    _cached_jwks = payload
    _jwks_cached_at = now
    return payload


def _key_from_jwks(token: str, *, force_refresh: bool = False) -> str:
    jwks_payload = _fetch_jwks(force_refresh=force_refresh)
    keys = jwks_payload.get("keys") or []
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwk_data = None
    if kid:
        jwk_data = next((item for item in keys if item.get("kid") == kid), None)
    if jwk_data is None and keys:
        jwk_data = keys[0]
    if jwk_data is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return jwk.construct(jwk_data).to_pem().decode("utf-8")


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


def _decode_token(token: str, key: str) -> dict:
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=EXPECTED_AUDIENCE,
        issuer=EXPECTED_ISSUER,
    )


def _log_rejection(token: str, *, detail: str, exc: Exception | None = None) -> None:
    try:
        claims = jwt.get_unverified_claims(token)
        payload = {
            "iss": claims.get("iss"),
            "aud": claims.get("aud"),
            "sub": claims.get("sub"),
            "detail": detail,
        }
    except Exception:
        payload = {"detail": detail}
    if exc:
        payload["error"] = str(exc)
    _logger.warning("admin_auth.token_rejected", extra=payload)


def verify_admin_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key = _key_from_jwks(token)
        payload = _decode_token(token, public_key)
    except (JWTError, jwk.JWKError, ValueError, HTTPException) as exc:
        _logger.info(
            "admin_auth.decode_failed_refreshing_key",
            extra={"error": str(exc), "jwks_url": JWKS_URL},
        )
        public_key = _key_from_jwks(token, force_refresh=True)
        try:
            payload = _decode_token(token, public_key)
        except (JWTError, jwk.JWKError, ValueError) as inner_exc:
            _log_rejection(token, detail="invalid_token", exc=inner_exc)
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

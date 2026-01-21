from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from neft_shared.logging_setup import get_logger

from app.services.jwt_support import (
    DEFAULT_JWKS_URL,
    DEFAULT_PUBLIC_KEY_URL,
    classify_jwt_error,
    fetch_jwks as fetch_jwks_support,
    fetch_public_key,
    log_token_rejection,
    parse_allowed_algs,
    parse_expected_audience,
    resolve_jwks_key,
)

PUBLIC_KEY_URL = os.getenv(
    "ADMIN_PUBLIC_KEY_URL",
    os.getenv("AUTH_PUBLIC_KEY_URL", DEFAULT_PUBLIC_KEY_URL),
)
JWKS_URL = os.getenv(
    "ADMIN_JWKS_URL",
    os.getenv("AUTH_JWKS_URL", DEFAULT_JWKS_URL),
)
PUBLIC_KEY_CACHE_TTL = int(os.getenv("AUTH_PUBLIC_KEY_CACHE_TTL", "300"))
EXPECTED_ISSUER = os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))
EXPECTED_AUDIENCE = parse_expected_audience(
    os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-admin"))
)
ALLOWED_ALGS = parse_allowed_algs()

ADMIN_ROLES = {
    role.strip()
    for role in os.getenv("ADMIN_ROLES", os.getenv("NEFT_ADMIN_ROLES", "ADMIN")).split(",")
    if role.strip()
}
if not ADMIN_ROLES:
    ADMIN_ROLES = {"ADMIN"}

_logger = get_logger(__name__)


def _static_public_key() -> str | None:
    return os.getenv("ADMIN_PUBLIC_KEY")


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        _log_rejection("", reason="missing_token")
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not auth_header.startswith("Bearer "):
        _log_rejection("", reason="bad_format")
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        _log_rejection("", reason="missing_token")
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


def _decode_token(token: str, key: str) -> dict:
    return jwt.decode(
        token,
        key,
        algorithms=ALLOWED_ALGS,
        audience=EXPECTED_AUDIENCE,
        issuer=EXPECTED_ISSUER,
    )


def _log_rejection(token: str, *, reason: str, exc: Exception | None = None) -> None:
    log_token_rejection(
        _logger,
        token,
        reason=reason,
        event="admin_auth.token_rejected",
        exc=exc,
    )


def _resolve_public_key(token: str, *, force_refresh: bool = False) -> tuple[str, bool, bool]:
    if not force_refresh:
        static_key = _static_public_key()
        if static_key:
            return static_key, False, False

    if JWKS_URL:
        resolution = resolve_jwks_key(
            token,
            jwks_url=JWKS_URL,
            ttl=PUBLIC_KEY_CACHE_TTL,
            force_refresh=force_refresh,
            log_info=lambda event, payload: _logger.info(event, extra=payload),
            log_warning=lambda event, payload: _logger.warning(event, extra=payload),
            event_prefix="admin_auth",
        )
        return resolution.public_key, resolution.missing_kid, resolution.kid_not_found

    public_key = fetch_public_key(
        PUBLIC_KEY_URL,
        ttl=PUBLIC_KEY_CACHE_TTL,
        force_refresh=force_refresh,
        log_info=lambda event, payload: _logger.info(event, extra=payload),
        log_warning=lambda event, payload: _logger.warning(event, extra=payload),
        event_prefix="admin_auth",
    )
    return public_key, False, False


def get_public_key(*, force_refresh: bool = False) -> str:
    if not force_refresh:
        static_key = _static_public_key()
        if static_key:
            return static_key

    return fetch_public_key(
        PUBLIC_KEY_URL,
        ttl=PUBLIC_KEY_CACHE_TTL,
        force_refresh=force_refresh,
        log_info=lambda event, payload: _logger.info(event, extra=payload),
        log_warning=lambda event, payload: _logger.warning(event, extra=payload),
        event_prefix="admin_auth",
    )


def fetch_jwks(
    url: str | None = None,
    *,
    ttl: int = PUBLIC_KEY_CACHE_TTL,
    force_refresh: bool = False,
) -> dict:
    return fetch_jwks_support(
        url or JWKS_URL,
        ttl=ttl,
        force_refresh=force_refresh,
        log_info=lambda event, payload: _logger.info(event, extra=payload),
        log_warning=lambda event, payload: _logger.warning(event, extra=payload),
        event_prefix="admin_auth",
    )


def get_jwks(*, ttl: int = PUBLIC_KEY_CACHE_TTL, force_refresh: bool = False) -> dict:
    return fetch_jwks(ttl=ttl, force_refresh=force_refresh)


def verify_admin_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key, missing_kid, kid_not_found = _resolve_public_key(token)
        payload = _decode_token(token, public_key)
    except (JWTError, ValueError, HTTPException) as exc:
        _logger.info(
            "admin_auth.decode_failed_refreshing_key",
            extra={"error": str(exc), "jwks_url": JWKS_URL},
        )
        public_key, missing_kid, kid_not_found = _resolve_public_key(token, force_refresh=True)
        try:
            payload = _decode_token(token, public_key)
        except (JWTError, ValueError) as inner_exc:
            reason = classify_jwt_error(inner_exc)
            if kid_not_found:
                reason = "kid_not_found"
            _log_rejection(token, reason=reason, exc=inner_exc)
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

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
    parse_scopes,
    resolve_jwks_key,
)

PUBLIC_KEY_URL = os.getenv(
    "CLIENT_PUBLIC_KEY_URL",
    os.getenv("AUTH_PUBLIC_KEY_URL", DEFAULT_PUBLIC_KEY_URL),
)
JWKS_URL = os.getenv(
    "CLIENT_JWKS_URL",
    os.getenv("AUTH_JWKS_URL", DEFAULT_JWKS_URL),
)
PUBLIC_KEY_CACHE_TTL = int(os.getenv("AUTH_PUBLIC_KEY_CACHE_TTL", "300"))
EXPECTED_ISSUER = os.getenv(
    "NEFT_CLIENT_ISSUER",
    os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-client")),
)
EXPECTED_AUDIENCE = os.getenv(
    "NEFT_CLIENT_AUDIENCE",
    os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-client")),
)
ALLOWED_ALGS = parse_allowed_algs()

ALLOWED_CLIENT_ROLES = {
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_OWNER",
    "CLIENT_USER",
}

_logger = get_logger(__name__)


def _static_public_key() -> str | None:
    return os.getenv("CLIENT_PUBLIC_KEY") or os.getenv("ADMIN_PUBLIC_KEY")


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
        algorithms=ALLOWED_ALGS,
        audience=EXPECTED_AUDIENCE,
        issuer=EXPECTED_ISSUER,
    )


def _log_rejection(token: str, *, reason: str, exc: Exception | None = None) -> None:
    log_token_rejection(
        logger=_logger,
        token=token,
        reason=reason,
        event="client_auth.token_rejected",
        exc=exc,
    )


def _resolve_public_key(token: str, *, force_refresh: bool = False) -> tuple[str, bool]:
    if not force_refresh:
        static_key = _static_public_key()
        if static_key:
            return static_key, False

    if JWKS_URL:
        resolution = resolve_jwks_key(
            token,
            jwks_url=JWKS_URL,
            ttl=PUBLIC_KEY_CACHE_TTL,
            force_refresh=force_refresh,
            log_info=lambda event, payload: _logger.info(event, extra=payload),
            log_warning=lambda event, payload: _logger.warning(event, extra=payload),
            event_prefix="client_auth",
        )
        return resolution.public_key, resolution.missing_kid

    public_key = fetch_public_key(
        PUBLIC_KEY_URL,
        ttl=PUBLIC_KEY_CACHE_TTL,
        force_refresh=force_refresh,
        log_info=lambda event, payload: _logger.info(event, extra=payload),
        log_warning=lambda event, payload: _logger.warning(event, extra=payload),
        event_prefix="client_auth",
    )
    return public_key, False


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
        event_prefix="client_auth",
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
        event_prefix="client_auth",
    )


def get_jwks(*, ttl: int = PUBLIC_KEY_CACHE_TTL, force_refresh: bool = False) -> dict:
    return fetch_jwks(ttl=ttl, force_refresh=force_refresh)


def verify_client_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key, missing_kid = _resolve_public_key(token)
        payload = _decode_token(token, public_key)
    except (JWTError, ValueError, HTTPException):
        public_key, missing_kid = _resolve_public_key(token, force_refresh=True)
        try:
            payload = _decode_token(token, public_key)
        except (JWTError, ValueError) as inner_exc:
            reason = classify_jwt_error(inner_exc)
            if missing_kid and reason == "signature_invalid":
                reason = "no_kid"
            _log_rejection(token, reason=reason, exc=inner_exc)
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
    payload["scopes"] = parse_scopes(payload)
    return payload


def verify_onboarding_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key, missing_kid = _resolve_public_key(token)
        payload = _decode_token(token, public_key)
    except (JWTError, ValueError, HTTPException):
        public_key, missing_kid = _resolve_public_key(token, force_refresh=True)
        try:
            payload = _decode_token(token, public_key)
        except (JWTError, ValueError) as inner_exc:
            reason = classify_jwt_error(inner_exc)
            if missing_kid and reason == "signature_invalid":
                reason = "no_kid"
            _log_rejection(token, reason=reason, exc=inner_exc)
            raise HTTPException(status_code=401, detail="Invalid token")

    roles = payload.get("roles") or []
    role = payload.get("role") or next((r for r in roles if r in ALLOWED_CLIENT_ROLES), None)
    subject_type = payload.get("subject_type")
    if role not in ALLOWED_CLIENT_ROLES and subject_type != "client_user":
        raise HTTPException(status_code=403, detail="Forbidden")

    payload["user_id"] = payload.get("user_id") or payload.get("sub")
    if role:
        payload["role"] = role
    payload["scopes"] = parse_scopes(payload)
    return payload


def require_client_user(token: dict = Depends(verify_client_token)) -> dict:
    return token


def require_onboarding_user(token: dict = Depends(verify_onboarding_token)) -> dict:
    return token

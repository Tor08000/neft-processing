from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from neft_shared.logging_setup import get_logger

from uuid import uuid4

from app.services.jwt_support import (
    DEFAULT_JWKS_URL,
    DEFAULT_PUBLIC_KEY_URL,
    classify_jwt_error,
    detect_portal_mismatch,
    fetch_jwks as fetch_jwks_support,
    fetch_public_key,
    log_token_rejection,
    parse_allowed_algs,
    parse_scopes,
    resolve_jwks_key,
    should_refresh_jwks,
)

PUBLIC_KEY_URL = os.getenv(
    "PARTNER_PUBLIC_KEY_URL",
    os.getenv("AUTH_PUBLIC_KEY_URL", DEFAULT_PUBLIC_KEY_URL),
)
JWKS_URL = os.getenv(
    "PARTNER_JWKS_URL",
    os.getenv("AUTH_JWKS_URL", DEFAULT_JWKS_URL),
)
PUBLIC_KEY_CACHE_TTL = int(os.getenv("AUTH_PUBLIC_KEY_CACHE_TTL", "300"))
EXPECTED_ISSUER = os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))
EXPECTED_AUDIENCE = os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-admin"))
ALLOWED_ALGS = parse_allowed_algs()

_logger = get_logger(__name__)


def _static_public_key() -> str | None:
    return os.getenv("PARTNER_PUBLIC_KEY") or os.getenv("ADMIN_PUBLIC_KEY")


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
        logger=_logger,
        token=token,
        reason=reason,
        event="partner_auth.token_rejected",
        exc=exc,
    )


def _reject_wrong_portal(token: str, *, claims: dict | None = None) -> None:
    if detect_portal_mismatch(token, "partner", claims=claims):
        _log_rejection(token, reason="wrong_portal")
        raise HTTPException(
            status_code=401,
            detail={
                "detail": {
                    "error": "token_rejected",
                    "reason_code": "TOKEN_WRONG_PORTAL",
                    "error_id": str(uuid4()),
                }
            },
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
            event_prefix="partner_auth",
        )
        return resolution.public_key, resolution.missing_kid, resolution.kid_not_found

    public_key = fetch_public_key(
        PUBLIC_KEY_URL,
        ttl=PUBLIC_KEY_CACHE_TTL,
        force_refresh=force_refresh,
        log_info=lambda event, payload: _logger.info(event, extra=payload),
        log_warning=lambda event, payload: _logger.warning(event, extra=payload),
        event_prefix="partner_auth",
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
        event_prefix="partner_auth",
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
        event_prefix="partner_auth",
    )


def get_jwks(*, ttl: int = PUBLIC_KEY_CACHE_TTL, force_refresh: bool = False) -> dict:
    return fetch_jwks(ttl=ttl, force_refresh=force_refresh)


def verify_partner_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key, missing_kid, kid_not_found = _resolve_public_key(token)
    except HTTPException:
        raise

    try:
        payload = _decode_token(token, public_key)
    except (JWTError, ValueError) as exc:
        _reject_wrong_portal(token)
        reason = classify_jwt_error(exc)
        if should_refresh_jwks(reason, missing_kid=missing_kid, kid_not_found=kid_not_found):
            public_key, missing_kid, kid_not_found = _resolve_public_key(token, force_refresh=True)
            try:
                payload = _decode_token(token, public_key)
            except (JWTError, ValueError) as inner_exc:
                reason = classify_jwt_error(inner_exc)
                if kid_not_found:
                    reason = "kid_not_found"
                _log_rejection(token, reason=reason, exc=inner_exc)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": {
                            "type": "token_rejected",
                            "reason_code": "TOKEN_REJECTED",
                            "message": "Invalid token",
                        }
                    },
                )
        else:
            _log_rejection(token, reason=reason, exc=exc)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "type": "token_rejected",
                        "reason_code": "TOKEN_REJECTED",
                        "message": "Invalid token",
                    }
                },
            )

    _reject_wrong_portal(token, claims=payload)

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

    payload["user_id"] = payload.get("user_id") or payload.get("sub")
    payload["partner_id"] = partner_id
    payload["scopes"] = parse_scopes(payload)
    return payload


def require_partner_user(token: dict = Depends(verify_partner_token)) -> dict:
    return token


__all__ = [
    "fetch_jwks",
    "get_jwks",
    "get_public_key",
    "require_partner_user",
    "verify_partner_token",
]

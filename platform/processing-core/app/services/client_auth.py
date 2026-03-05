from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from neft_shared.logging_setup import get_logger

from uuid import uuid4

from app.services.session_status import ensure_session_active
from app.services.jwt_support import (
    DEFAULT_JWKS_URL,
    DEFAULT_PUBLIC_KEY_URL,
    classify_jwt_error,
    detect_portal_mismatch,
    fetch_jwks as fetch_jwks_support,
    fetch_public_key,
    log_token_rejection,
    parse_allowed_algs,
    parse_expected_audience,
    parse_scopes,
    resolve_jwks_key,
    should_refresh_jwks,
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
    os.getenv("CLIENT_AUTH_ISSUER", os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))),
)
EXPECTED_AUDIENCE = parse_expected_audience(
    os.getenv(
        "NEFT_CLIENT_AUDIENCE",
        os.getenv(
            "CLIENT_AUTH_AUDIENCE",
            os.getenv("ALLOWED_AUDIENCES", "neft-client"),
        ),
    )
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
    if not auth_header:
        _log_rejection("", reason="missing_header", path=str(request.url.path))
        raise _client_auth_http_error("missing_header")
    if not auth_header.startswith("Bearer "):
        _log_rejection("", reason="bad_scheme", path=str(request.url.path))
        raise _client_auth_http_error("bad_scheme")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        _log_rejection("", reason="missing_header", path=str(request.url.path))
        raise _client_auth_http_error("missing_header")

    return token


def _decode_token(token: str, key: str) -> dict:
    return jwt.decode(
        token,
        key,
        algorithms=ALLOWED_ALGS,
        audience=EXPECTED_AUDIENCE,
        issuer=EXPECTED_ISSUER,
    )


def _log_rejection(token: str, *, reason: str, exc: Exception | None = None, path: str | None = None) -> None:
    key_source = "public_key" if PUBLIC_KEY_URL else ("jwks" if JWKS_URL else "none")
    key_url = PUBLIC_KEY_URL or JWKS_URL
    log_token_rejection(
        logger=_logger,
        token=token,
        reason=reason,
        event="client_auth.token_rejected",
        exc=exc,
        path=path,
        key_source=key_source,
        key_url=key_url,
    )


def _reject_wrong_portal(token: str, *, claims: dict | None = None) -> None:
    if detect_portal_mismatch(token, "client", claims=claims):
        _log_rejection(token, reason="portal_mismatch")
        raise _client_auth_http_error("portal_mismatch")


def _client_auth_http_error(reason: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={
            "error": "client_token_missing_or_invalid",
            "reason": reason,
            "error_id": str(uuid4()),
        },
        headers={"X-Auth-Reason": reason},
    )


def _resolve_public_key(token: str, *, force_refresh: bool = False) -> tuple[str, bool, bool]:
    if not force_refresh:
        static_key = _static_public_key()
        if static_key:
            return static_key, False, False

    if PUBLIC_KEY_URL:
        public_key = fetch_public_key(
            PUBLIC_KEY_URL,
            ttl=PUBLIC_KEY_CACHE_TTL,
            force_refresh=force_refresh,
            log_info=lambda event, payload: _logger.info(event, extra=payload),
            log_warning=lambda event, payload: _logger.warning(event, extra=payload),
            event_prefix="client_auth",
        )
        return public_key, False, False

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
        return resolution.public_key, resolution.missing_kid, resolution.kid_not_found

    raise HTTPException(status_code=503, detail="No key source configured")


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
        public_key, missing_kid, kid_not_found = _resolve_public_key(token)
    except HTTPException:
        raise
    except Exception as exc:
        _log_rejection(token, reason="key_resolution_failed", exc=exc)
        raise _client_auth_http_error("decode_failed") from exc

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
                if reason == "iss_mismatch":
                    raise _client_auth_http_error("issuer_mismatch")
                if reason == "aud_mismatch":
                    raise _client_auth_http_error("audience_mismatch")
                raise _client_auth_http_error("decode_failed")
        else:
            _log_rejection(token, reason=reason, exc=exc)
            if reason == "iss_mismatch":
                raise _client_auth_http_error("issuer_mismatch")
            if reason == "aud_mismatch":
                raise _client_auth_http_error("audience_mismatch")
            raise _client_auth_http_error("decode_failed")
    except Exception as exc:
        _reject_wrong_portal(token)
        _log_rejection(token, reason="decode_failed", exc=exc)
        raise _client_auth_http_error("decode_failed") from exc

    _reject_wrong_portal(token, claims=payload)
    ensure_session_active(payload)

    roles = payload.get("roles") or []
    role = payload.get("role") or next((r for r in roles if r in ALLOWED_CLIENT_ROLES), None)
    subject_type = payload.get("subject_type")
    if role not in ALLOWED_CLIENT_ROLES and subject_type != "client_user":
        raise HTTPException(status_code=403, detail="Forbidden")

    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")

    payload["user_id"] = payload.get("user_id") or payload.get("sub")
    if role:
        payload["role"] = role
    payload["client_id"] = client_id
    payload["scopes"] = parse_scopes(payload)
    return payload


def verify_onboarding_token(token: str = Depends(_get_bearer_token)) -> dict:
    try:
        public_key, missing_kid, kid_not_found = _resolve_public_key(token)
    except HTTPException:
        raise
    except Exception as exc:
        _log_rejection(token, reason="key_resolution_failed", exc=exc)
        raise _client_auth_http_error("decode_failed") from exc

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
                if reason == "iss_mismatch":
                    raise _client_auth_http_error("issuer_mismatch")
                if reason == "aud_mismatch":
                    raise _client_auth_http_error("audience_mismatch")
                raise _client_auth_http_error("decode_failed")
        else:
            _log_rejection(token, reason=reason, exc=exc)
            if reason == "iss_mismatch":
                raise _client_auth_http_error("issuer_mismatch")
            if reason == "aud_mismatch":
                raise _client_auth_http_error("audience_mismatch")
            raise _client_auth_http_error("decode_failed")
    except Exception as exc:
        _reject_wrong_portal(token)
        _log_rejection(token, reason="decode_failed", exc=exc)
        raise _client_auth_http_error("decode_failed") from exc

    _reject_wrong_portal(token, claims=payload)

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

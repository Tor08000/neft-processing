from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests
from fastapi import HTTPException
from jose import JWTError, jwk, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

DEFAULT_JWKS_URL = os.getenv("AUTH_JWKS_URL", "http://auth-host:8000/api/auth/.well-known/jwks.json")
DEFAULT_PUBLIC_KEY_URL = os.getenv(
    "AUTH_PUBLIC_KEY_URL",
    "http://auth-host:8000/api/auth/v1/auth/public-key",
)
DEFAULT_CACHE_TTL = int(os.getenv("AUTH_PUBLIC_KEY_CACHE_TTL", "300"))


@dataclass
class JwksKeyResolution:
    public_key: str
    header: dict
    selected_kid: str | None
    missing_kid: bool = False
    kid_not_found: bool = False


_jwks_cache: dict[str, tuple[float, dict]] = {}
_public_key_cache: dict[str, tuple[float, str]] = {}


def parse_allowed_algs(default: str = "RS256") -> list[str]:
    raw = os.getenv("NEFT_AUTH_ALLOWED_ALGS", os.getenv("AUTH_ALLOWED_ALGS", default))
    algs = [item.strip() for item in raw.split(",") if item.strip()]
    return algs or [default]


def parse_scopes(claims: dict) -> list[str]:
    scopes = claims.get("scopes") or claims.get("scope") or []
    if isinstance(scopes, str):
        return [scope for scope in scopes.split() if scope]
    if isinstance(scopes, (list, tuple, set)):
        return [str(scope) for scope in scopes if str(scope)]
    return []


def get_unverified_header(token: str) -> dict:
    try:
        return jwt.get_unverified_header(token)
    except JWTError:
        return {}


def get_unverified_claims(token: str) -> dict:
    try:
        return jwt.get_unverified_claims(token)
    except JWTError:
        return {}


def _normalize_audience(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    return {str(value)}


def _collect_roles_for_detection(claims: dict) -> set[str]:
    roles: set[str] = set()
    raw_roles = claims.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    for role in raw_roles:
        if role:
            roles.add(str(role))
    if claims.get("role"):
        roles.add(str(claims["role"]))
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        realm_roles = realm_access.get("roles") or []
        if isinstance(realm_roles, str):
            realm_roles = [realm_roles]
        for role in realm_roles:
            if role:
                roles.add(str(role))
    return roles


def detect_token_kind(claims: dict) -> str:
    issuer = str(claims.get("iss") or "")
    audiences = _normalize_audience(claims.get("aud"))
    subject_type = str(claims.get("subject_type") or "")
    token_use = str(claims.get("token_use") or claims.get("typ") or "")
    realm = str(claims.get("realm") or "")
    azp = str(claims.get("azp") or "")
    roles = _collect_roles_for_detection(claims)

    client_issuer = os.getenv(
        "NEFT_CLIENT_ISSUER",
        os.getenv("CLIENT_AUTH_ISSUER", "neft-client"),
    )
    client_audience = os.getenv(
        "NEFT_CLIENT_AUDIENCE",
        os.getenv("CLIENT_AUTH_AUDIENCE", "neft-client"),
    )
    admin_issuer = os.getenv("NEFT_AUTH_ISSUER", os.getenv("AUTH_ISSUER", "neft-auth"))
    admin_audience = os.getenv("NEFT_AUTH_AUDIENCE", os.getenv("AUTH_AUDIENCE", "neft-admin"))

    normalized_roles = {role.upper() for role in roles}
    subject_type_normalized = subject_type.strip().lower()
    token_use_normalized = token_use.strip().lower()

    if issuer == client_issuer or client_audience in audiences:
        return "client"
    if subject_type_normalized == "client_user" or any(role.startswith("CLIENT_") for role in normalized_roles):
        return "client"
    if claims.get("client_id"):
        return "client"

    if subject_type_normalized == "partner_user" or any(role.startswith("PARTNER_") for role in normalized_roles):
        return "partner"
    if claims.get("partner_id"):
        return "partner"
    if "partner" in token_use_normalized or "partner" in azp.lower() or "partner" in realm.lower():
        return "partner"

    if issuer == admin_issuer or admin_audience in audiences:
        return "admin"
    if any(role.startswith("ADMIN") for role in normalized_roles):
        return "admin"

    return "admin"


def classify_jwt_error(exc: Exception) -> str:
    if isinstance(exc, ExpiredSignatureError):
        return "expired"
    if isinstance(exc, JWTClaimsError):
        msg = str(exc).lower()
        if "nbf" in msg or "not yet valid" in msg:
            return "nbf"
        if "aud" in msg or "audience" in msg:
            return "aud_mismatch"
        if "issuer" in msg or "iss" in msg:
            return "iss_mismatch"
        if "alg" in msg or "algorithm" in msg:
            return "alg_mismatch"
        return "invalid_claims"
    if isinstance(exc, JWTError):
        msg = str(exc).lower()
        if "signature" in msg:
            return "signature_invalid"
        if "alg" in msg or "algorithm" in msg:
            return "alg_mismatch"
        if "segments" in msg or "format" in msg or "malformed" in msg:
            return "bad_format"
    return "invalid_token"


def log_token_rejection(
    logger: Any,
    token: str,
    *,
    reason: str,
    event: str,
    exc: Exception | None = None,
) -> None:
    header = get_unverified_header(token)
    claims = get_unverified_claims(token)
    payload = {
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "alg": header.get("alg"),
        "kid": header.get("kid"),
        "subject": claims.get("sub"),
        "reason": reason,
    }
    if exc is not None:
        payload["error"] = str(exc)
    logger.warning(event, extra=payload)


def _fetch_cached(
    cache: dict[str, tuple[float, Any]],
    url: str,
    *,
    ttl: int,
    force_refresh: bool,
) -> Any | None:
    if force_refresh:
        return None
    cached = cache.get(url)
    if not cached:
        return None
    cached_at, value = cached
    if time.time() - cached_at < ttl:
        return value
    return None


def fetch_public_key(
    url: str,
    *,
    ttl: int = DEFAULT_CACHE_TTL,
    force_refresh: bool = False,
    log_info: Callable[[str, dict], None] | None = None,
    log_warning: Callable[[str, dict], None] | None = None,
    event_prefix: str = "auth",
) -> str:
    cached = _fetch_cached(_public_key_cache, url, ttl=ttl, force_refresh=force_refresh)
    if cached:
        return cached

    try:
        response = requests.get(url, timeout=5)
        if log_info:
            log_info(f"{event_prefix}.public_key.refresh", {"url": url, "status_code": response.status_code})
        response.raise_for_status()
        key = response.text
    except requests.RequestException as exc:  # pragma: no cover - network errors
        if log_warning:
            log_warning(f"{event_prefix}.public_key.refresh_failed", {"url": url, "error": str(exc)})
        raise HTTPException(status_code=503, detail="Unable to fetch public key") from exc

    _public_key_cache[url] = (time.time(), key)
    return key


def fetch_jwks(
    url: str,
    *,
    ttl: int = DEFAULT_CACHE_TTL,
    force_refresh: bool = False,
    log_info: Callable[[str, dict], None] | None = None,
    log_warning: Callable[[str, dict], None] | None = None,
    event_prefix: str = "auth",
) -> dict:
    cached = _fetch_cached(_jwks_cache, url, ttl=ttl, force_refresh=force_refresh)
    if cached:
        return cached

    try:
        response = requests.get(url, timeout=5)
        if log_info:
            log_info(f"{event_prefix}.jwks.refresh", {"url": url, "status_code": response.status_code})
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        if log_warning:
            log_warning(f"{event_prefix}.jwks.refresh_failed", {"url": url, "error": str(exc)})
        raise HTTPException(status_code=503, detail="Unable to fetch JWKS") from exc
    except ValueError as exc:
        if log_warning:
            log_warning(f"{event_prefix}.jwks.invalid_payload", {"url": url, "error": str(exc)})
        raise HTTPException(status_code=503, detail="Unable to parse JWKS") from exc

    if not isinstance(payload, dict) or "keys" not in payload:
        if log_warning:
            log_warning(f"{event_prefix}.jwks.invalid_payload", {"url": url, "detail": "missing_keys"})
        raise HTTPException(status_code=503, detail="Invalid JWKS payload")

    _jwks_cache[url] = (time.time(), payload)
    return payload


def resolve_jwks_key(
    token: str,
    *,
    jwks_url: str,
    ttl: int = DEFAULT_CACHE_TTL,
    force_refresh: bool = False,
    log_info: Callable[[str, dict], None] | None = None,
    log_warning: Callable[[str, dict], None] | None = None,
    event_prefix: str = "auth",
) -> JwksKeyResolution:
    header = get_unverified_header(token)
    kid = header.get("kid")
    kid_not_found = False

    jwks_payload = fetch_jwks(
        jwks_url,
        ttl=ttl,
        force_refresh=force_refresh,
        log_info=log_info,
        log_warning=log_warning,
        event_prefix=event_prefix,
    )
    keys = jwks_payload.get("keys") or []

    jwk_data = None
    if kid:
        jwk_data = next((item for item in keys if item.get("kid") == kid), None)
        if jwk_data is None and keys:
            kid_not_found = True
    if jwk_data is None and keys:
        jwk_data = keys[0]
    if jwk_data is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    public_key = jwk.construct(jwk_data).to_pem().decode("utf-8")
    return JwksKeyResolution(
        public_key=public_key,
        header=header,
        selected_kid=jwk_data.get("kid"),
        missing_kid=not bool(kid),
        kid_not_found=kid_not_found,
    )

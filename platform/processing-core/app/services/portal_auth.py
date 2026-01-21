from __future__ import annotations

from fastapi import HTTPException, Request

from app.services import admin_auth, client_auth, partner_auth
from app.services.jwt_support import detect_token_kind, get_unverified_claims


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


def _normalize_org_id(payload: dict) -> dict:
    org_id = payload.get("client_id") or payload.get("partner_id") or payload.get("org_id")
    if org_id:
        payload["org_id"] = org_id
    return payload


def _verify_by_kind(token: str, *, allow_admin: bool) -> dict:
    claims = get_unverified_claims(token)
    token_kind = detect_token_kind(claims)
    if token_kind == "client":
        payload = client_auth.verify_onboarding_token(token=token)
        return _normalize_org_id(payload)
    if token_kind == "partner":
        payload = partner_auth.verify_partner_token(token=token)
        return _normalize_org_id(payload)
    if token_kind == "admin":
        if not allow_admin:
            raise HTTPException(status_code=403, detail="forbidden")
        payload = admin_auth.verify_admin_token(token=token)
        return _normalize_org_id(payload)
    payload = client_auth.verify_onboarding_token(token=token)
    return _normalize_org_id(payload)


def verify_portal_token(request: Request) -> dict:
    token = _get_bearer_token(request)
    return _verify_by_kind(token, allow_admin=False)


def verify_portal_or_admin_token(request: Request) -> dict:
    token = _get_bearer_token(request)
    return _verify_by_kind(token, allow_admin=True)


def require_portal_user(request: Request) -> dict:
    return verify_portal_token(request)


def require_portal_or_admin_user(request: Request) -> dict:
    return verify_portal_or_admin_token(request)


__all__ = [
    "require_portal_user",
    "require_portal_or_admin_user",
    "verify_portal_token",
    "verify_portal_or_admin_token",
]

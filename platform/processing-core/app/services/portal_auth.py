from __future__ import annotations

from fastapi import HTTPException, Request

from app.services import client_auth, partner_auth


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


def verify_portal_token(request: Request) -> dict:
    token = _get_bearer_token(request)
    errors: list[HTTPException] = []

    for verifier in (client_auth.verify_onboarding_token, partner_auth.verify_partner_token):
        try:
            payload = verifier(token=token)
        except HTTPException as exc:
            errors.append(exc)
            continue
        org_id = payload.get("client_id") or payload.get("partner_id") or payload.get("org_id")
        if org_id:
            payload["org_id"] = org_id
        return payload

    status_codes = {exc.status_code for exc in errors}
    if 403 in status_codes:
        raise HTTPException(status_code=403, detail="forbidden")
    raise HTTPException(status_code=401, detail="invalid_token")


def require_portal_user(request: Request) -> dict:
    return verify_portal_token(request)


__all__ = ["require_portal_user", "verify_portal_token"]

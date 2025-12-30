from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.services import admin_auth, client_auth, partner_auth


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


def support_user(request: Request) -> dict:
    token = _get_bearer_token(request)
    try:
        payload = admin_auth.verify_admin_token(token)
        payload["is_admin"] = True
        return payload
    except HTTPException:
        pass

    try:
        payload = partner_auth.verify_partner_token(token)
        payload["is_partner"] = True
        return payload
    except HTTPException:
        payload = client_auth.verify_client_token(token)
        payload["is_client"] = True
        return payload


def support_user_dep(token: dict = Depends(support_user)) -> dict:
    return token


__all__ = ["support_user_dep"]

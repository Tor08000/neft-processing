from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.services import admin_auth, client_auth


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


def bi_user(request: Request) -> dict:
    token = _get_bearer_token(request)
    try:
        payload = admin_auth.verify_admin_token(token)
    except HTTPException:
        payload = client_auth.verify_client_token(token)

    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant_context")

    return payload


def bi_user_dep(token: dict = Depends(bi_user)) -> dict:
    return token


__all__ = ["bi_user_dep"]

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request

from app.services import admin_auth, client_auth, partner_auth


def _is_uuid_like(value: object) -> bool:
    if value in (None, ""):
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _resolve_support_partner_payload(payload: dict) -> dict:
    subject_type = str(payload.get("subject_type") or "").strip().lower()
    raw_partner_id = payload.get("partner_id")
    if subject_type != "partner_user" or _is_uuid_like(raw_partner_id):
        return payload
    try:
        from app.db import get_sessionmaker
        from app.services.partner_context import resolve_partner_id_from_claims
    except Exception:
        return payload

    db = get_sessionmaker()()
    try:
        canonical_partner_id = resolve_partner_id_from_claims(db, claims=payload)
    except Exception:
        canonical_partner_id = None
    finally:
        db.close()

    if not canonical_partner_id:
        return payload

    resolved_payload = dict(payload)
    resolved_payload["partner_id"] = str(canonical_partner_id)
    return resolved_payload


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
        payload = _resolve_support_partner_payload(partner_auth.verify_partner_token(token))
        payload["is_partner"] = True
        return payload
    except HTTPException:
        payload = client_auth.verify_client_token(token)
        payload["is_client"] = True
        return payload


def support_user_dep(token: dict = Depends(support_user)) -> dict:
    return token


__all__ = ["support_user_dep"]

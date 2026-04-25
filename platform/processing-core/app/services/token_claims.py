from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.crm import CRMClient
from app.services.subscription_service import DEFAULT_TENANT_ID


def token_email(token: dict | None) -> str | None:
    if not token:
        return None
    raw_email = token.get("email")
    if raw_email is not None:
        email = str(raw_email).strip()
        if email:
            return email
    raw_subject = token.get("sub")
    if raw_subject is None:
        return None
    subject = str(raw_subject).strip()
    if subject and "@" in subject:
        return subject
    return None


def token_tenant_id(token: dict | None) -> int | None:
    if not token:
        return None
    raw_tenant_id = token.get("tenant_id")
    if raw_tenant_id is None:
        return None
    if isinstance(raw_tenant_id, int):
        return raw_tenant_id
    tenant_id = str(raw_tenant_id).strip()
    if tenant_id.isdigit():
        return int(tenant_id)
    return None


def resolve_token_tenant_id(
    token: dict | None,
    *,
    db: Session | None = None,
    client_id: str | None = None,
    default: int | None = None,
    error_detail: str = "missing_tenant_context",
) -> int:
    resolved = token_tenant_id(token)
    if resolved is not None:
        return resolved

    candidate_client_id = str(client_id or (token or {}).get("client_id") or "").strip() or None
    if db is not None and candidate_client_id:
        try:
            resolved = db.query(CRMClient.tenant_id).filter(CRMClient.id == candidate_client_id).scalar()
        except SQLAlchemyError:
            resolved = None
        if resolved is not None:
            return int(resolved)

    if default is not None:
        return int(default)

    raise HTTPException(status_code=403, detail=error_detail)


__all__ = [
    "DEFAULT_TENANT_ID",
    "resolve_token_tenant_id",
    "token_email",
    "token_tenant_id",
]

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.kpi import KpiSummary
from app.services import admin_auth, client_auth
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id
from app.services.kpi_service import build_kpi_summary

router = APIRouter(prefix="/kpi", tags=["kpi"])

ADMIN_OVERRIDE_ROLES = {"ADMIN", "PLATFORM_ADMIN", "SUPERADMIN"}


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _normalize_roles(token: dict) -> set[str]:
    roles = set()
    role = token.get("role")
    if role:
        roles.add(str(role).upper())
    raw_roles = token.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles.update({str(item).upper() for item in raw_roles})
    return roles


def _resolve_token_context(request: Request) -> tuple[str, dict]:
    token = _get_bearer_token(request)
    try:
        return "admin", admin_auth.verify_admin_token(token)
    except HTTPException:
        return "client", client_auth.verify_client_token(token)


def _resolve_tenant_id(
    *,
    db: Session,
    token: dict,
    token_type: str,
    tenant_override: int | None,
) -> tuple[int, str | None]:
    if token_type == "admin":
        roles = _normalize_roles(token)
        if tenant_override is not None:
            if not roles.intersection(ADMIN_OVERRIDE_ROLES):
                raise HTTPException(status_code=403, detail="forbidden")
            return tenant_override, None
        return resolve_token_tenant_id(token, error_detail="Missing tenant context"), None

    if tenant_override is not None:
        raise HTTPException(status_code=403, detail="forbidden")
    client_id = str(token.get("client_id") or "") or None
    return (
        resolve_token_tenant_id(
            token,
            db=db,
            client_id=client_id,
            default=DEFAULT_TENANT_ID,
            error_detail="Missing tenant context",
        ),
        client_id,
    )


@router.get("/summary", response_model=KpiSummary)
def kpi_summary(
    request: Request,
    db: Session = Depends(get_db),
    window_days: Literal[7, 30] = Query(7),
    tenant_id: int | None = Query(None, ge=1),
) -> KpiSummary:
    token_type, token = _resolve_token_context(request)
    resolved_tenant_id, client_id = _resolve_tenant_id(
        db=db,
        token=token,
        token_type=token_type,
        tenant_override=tenant_id,
    )
    return build_kpi_summary(
        db,
        tenant_id=resolved_tenant_id,
        window_days=window_days,
        client_id=client_id if token_type == "client" else None,
    )


__all__ = ["router"]

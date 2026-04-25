from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogOut, AuditSearchResponse, AuditVerifyRequest, AuditVerifyResponse
from app.services.audit_service import AuditService


AUDIT_VIEW_ROLES = {
    role.strip().upper()
    for role in os.getenv(
        "AUDIT_VIEW_ROLES",
        "SUPERADMIN,PLATFORM_ADMIN,FINANCE,AUDITOR,ADMIN",
    ).split(",")
    if role.strip()
}


def require_audit_role(token: dict = Depends(require_admin_user)) -> dict:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role and role not in roles:
        roles.append(role)
    normalized_roles = {str(item).upper() for item in roles}
    if not normalized_roles.intersection(AUDIT_VIEW_ROLES):
        raise HTTPException(status_code=403, detail="Forbidden")
    return token


router = APIRouter(prefix="/api/v1/audit", tags=["audit"], dependencies=[Depends(require_audit_role)])


@router.get("/search", response_model=AuditSearchResponse)
def search_audit(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    event_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    external_ref: str | None = Query(None),
    provider: str | None = Query(None),
    actor_id: str | None = Query(None),
    actor_email: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query("ts.desc"),
    db: Session = Depends(get_db),
) -> AuditSearchResponse:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if date_from:
        query = query.filter(AuditLog.ts >= date_from)
    if date_to:
        query = query.filter(AuditLog.ts <= date_to)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if actor_email:
        query = query.filter(AuditLog.actor_email == actor_email)
    if external_ref:
        if getattr(getattr(db.get_bind(), "dialect", None), "name", None) == "sqlite":
            query = query.filter(func.json_extract(AuditLog.external_refs, "$.external_ref") == external_ref)
            if provider:
                query = query.filter(func.json_extract(AuditLog.external_refs, "$.provider") == provider)
        else:
            payload = {"external_ref": external_ref}
            if provider:
                payload["provider"] = provider
            query = query.filter(AuditLog.external_refs.contains(payload))

    total = query.count()
    if sort == "ts.asc":
        query = query.order_by(AuditLog.ts.asc(), AuditLog.id.asc())
    else:
        query = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc())

    items = query.offset(offset).limit(limit).all()
    return AuditSearchResponse(
        items=[AuditLogOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=AuditSearchResponse)
def entity_timeline(
    entity_type: str,
    entity_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AuditSearchResponse:
    query = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type)
        .filter(AuditLog.entity_id == entity_id)
    )
    total = query.count()
    items = (
        query.order_by(AuditLog.ts.asc(), AuditLog.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return AuditSearchResponse(
        items=[AuditLogOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/verify", response_model=AuditVerifyResponse)
def verify_chain(payload: AuditVerifyRequest, db: Session = Depends(get_db)) -> AuditVerifyResponse:
    service = AuditService(db)
    result = service.verify_chain(date_from=payload.from_ts, date_to=payload.to_ts, tenant_id=payload.tenant_id)
    return AuditVerifyResponse(
        status=result["status"],
        checked=result["checked"],
        broken_at_id=result.get("broken_at_id"),
        message=result.get("message"),
    )


__all__ = ["router"]

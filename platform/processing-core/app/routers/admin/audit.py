from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.audit_retention import AuditLegalHoldScope
from app.schemas.admin.audit import AdminAuditCorrelationResponse, AdminAuditEvent, AdminAuditFeedResponse
from app.schemas.admin.audit_retention import AuditLegalHoldCreate, AuditLegalHoldOut
from app.schemas.admin.audit_signing import AuditSigningKeyOut, AuditSigningKeysResponse
from app.services.admin_auth import require_admin
from app.services.audit_retention_service import create_legal_hold, disable_legal_hold, list_legal_holds
from app.services.audit_signing import AuditSigningService
from app.security.rbac.guard import require_permission

router = APIRouter(prefix="/audit", tags=["admin-audit"], dependencies=[Depends(require_permission("admin:audit:*"))])


def _audit_event_from_log(log: AuditLog) -> AdminAuditEvent:
    correlation_id = None
    if isinstance(log.external_refs, dict):
        correlation_id = log.external_refs.get("correlation_id")
    actor = log.actor_email or log.actor_id
    payload = {
        "before": log.before,
        "after": log.after,
        "diff": log.diff,
    }
    payload = {key: value for key, value in payload.items() if value is not None} or None
    return AdminAuditEvent(
        id=str(log.id),
        ts=log.ts,
        type=log.event_type,
        action=log.action,
        title=log.event_type,
        actor=actor,
        reason=log.reason,
        correlation_id=correlation_id,
        meta=log.external_refs,
        payload=payload,
    )


@router.get("", response_model=AdminAuditFeedResponse)
def list_audit_events(
    type: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AdminAuditFeedResponse:
    query = db.query(AuditLog)
    if type:
        type_filters = [item.strip() for item in type.split(",") if item.strip()]
        if type_filters:
            clauses = [AuditLog.event_type.ilike(f"%{item}%") for item in type_filters]
            query = query.filter(or_(*clauses))
    if correlation_id:
        query = query.filter(AuditLog.external_refs.contains({"correlation_id": correlation_id}))
    if search:
        search_value = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.actor_id.ilike(search_value),
                AuditLog.actor_email.ilike(search_value),
                AuditLog.entity_id.ilike(search_value),
                AuditLog.entity_type.ilike(search_value),
                AuditLog.action.ilike(search_value),
                AuditLog.event_type.ilike(search_value),
            )
        )
    total = query.count()
    logs = query.order_by(AuditLog.ts.desc()).offset(offset).limit(limit).all()
    return AdminAuditFeedResponse(
        items=[_audit_event_from_log(item) for item in logs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{correlation_id}", response_model=AdminAuditCorrelationResponse)
def get_audit_chain(
    correlation_id: str,
    db: Session = Depends(get_db),
) -> AdminAuditCorrelationResponse:
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.external_refs.contains({"correlation_id": correlation_id}))
        .order_by(AuditLog.ts.asc())
        .all()
    )
    events = [_audit_event_from_log(item) for item in logs]
    return AdminAuditCorrelationResponse(
        correlation_id=correlation_id,
        items=events,
        events=events,
        chain=[correlation_id],
    )


@router.post("/holds", response_model=AuditLegalHoldOut)
def create_legal_hold_endpoint(
    payload: AuditLegalHoldCreate,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> AuditLegalHoldOut:
    if payload.scope == AuditLegalHoldScope.CASE and not payload.case_id:
        raise HTTPException(status_code=400, detail="case_id_required")
    if payload.scope != AuditLegalHoldScope.CASE and payload.case_id:
        raise HTTPException(status_code=400, detail="case_id_not_allowed")
    created_by = token.get("user_id") or token.get("sub")
    hold = create_legal_hold(
        db,
        scope=payload.scope,
        case_id=payload.case_id,
        reason=payload.reason,
        created_by=str(created_by) if created_by else None,
    )
    db.commit()
    db.refresh(hold)
    return AuditLegalHoldOut.model_validate(hold)


@router.post("/holds/{hold_id}/disable", response_model=AuditLegalHoldOut)
def disable_legal_hold_endpoint(
    hold_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> AuditLegalHoldOut:
    _ = token
    hold = disable_legal_hold(db, hold_id=hold_id)
    if not hold:
        raise HTTPException(status_code=404, detail="hold_not_found")
    db.commit()
    db.refresh(hold)
    return AuditLegalHoldOut.model_validate(hold)


@router.get("/holds", response_model=list[AuditLegalHoldOut])
def list_legal_holds_endpoint(
    case_id: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[AuditLegalHoldOut]:
    holds = list_legal_holds(db, case_id=case_id, active_only=active_only)
    return [AuditLegalHoldOut.model_validate(item) for item in holds]


@router.get("/signing/keys", response_model=AuditSigningKeysResponse)
def list_audit_signing_keys_endpoint(
    token: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditSigningKeysResponse:
    _ = token
    service = AuditSigningService()
    keys = [AuditSigningKeyOut.model_validate(item) for item in service.list_keys(db=db)]
    return AuditSigningKeysResponse(keys=keys)


__all__ = ["router"]

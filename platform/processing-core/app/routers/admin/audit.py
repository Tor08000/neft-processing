from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit_retention import AuditLegalHoldScope
from app.schemas.admin.audit_retention import AuditLegalHoldCreate, AuditLegalHoldOut
from app.schemas.admin.audit_signing import AuditSigningKeyOut, AuditSigningKeysResponse
from app.services.admin_auth import require_admin
from app.services.audit_retention_service import create_legal_hold, disable_legal_hold, list_legal_holds
from app.services.audit_signing import AuditSigningService
from app.security.rbac.guard import require_permission

router = APIRouter(prefix="/audit", tags=["admin-audit"], dependencies=[Depends(require_permission("admin:audit:*"))])


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

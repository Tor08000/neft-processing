from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.ops import OpsEscalation, OpsEscalationStatus, OpsEscalationTarget
from app.schemas.admin.ops import OpsEscalationListResponse, OpsEscalationOut, OpsEscalationScanResponse
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.ops.escalations import ack_escalation, close_escalation, list_escalations, scan_explain_sla_expiry
from app.services.policy import actor_from_token

router = APIRouter(prefix="/ops", tags=["ops-escalations"])

_TARGET_ROLE_MAP = {
    OpsEscalationTarget.CRM: {"CRM", "ADMIN_CRM", "SUPERADMIN"},
    OpsEscalationTarget.COMPLIANCE: {"COMPLIANCE", "ADMIN_COMPLIANCE", "SUPERADMIN"},
    OpsEscalationTarget.LOGISTICS: {"OPS", "LOGISTICS", "ADMIN_OPS", "ADMIN_LOGISTICS", "SUPERADMIN"},
    OpsEscalationTarget.FINANCE: {"FINANCE", "ADMIN_FINANCE", "SUPERADMIN"},
}


def _require_target_access(token: dict, target: OpsEscalationTarget | None) -> None:
    actor = actor_from_token(token)
    roles = {role.upper() for role in (actor.roles or [])}
    if target:
        allowed = _TARGET_ROLE_MAP.get(target, set())
        if roles.intersection(allowed):
            return
        raise HTTPException(status_code=403, detail="forbidden")

    if any(roles.intersection(values) for values in _TARGET_ROLE_MAP.values()):
        return
    raise HTTPException(status_code=403, detail="forbidden")


def _tenant_id_from_token(token: dict) -> int:
    return int(token.get("tenant_id") or 0)


@router.get("/escalations", response_model=OpsEscalationListResponse)
def admin_list_escalations(
    target: OpsEscalationTarget | None = Query(None),
    status: OpsEscalationStatus | None = Query(None),
    client_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsEscalationListResponse:
    _require_target_access(token, target)
    tenant_id = _tenant_id_from_token(token)
    items, total = list_escalations(
        db,
        tenant_id=tenant_id,
        target=target,
        status=status,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )
    return OpsEscalationListResponse(
        items=[OpsEscalationOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/escalations/{escalation_id}/ack", response_model=OpsEscalationOut)
def admin_ack_escalation(
    escalation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsEscalationOut:
    escalation = db.get(OpsEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="escalation_not_found")
    _require_target_access(token, escalation.target)
    audit = AuditService(db)
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    updated = ack_escalation(db, escalation=escalation, audit=audit, request_ctx=request_ctx)
    db.commit()
    db.refresh(updated)
    return OpsEscalationOut.model_validate(updated)


@router.post("/escalations/{escalation_id}/close", response_model=OpsEscalationOut)
def admin_close_escalation(
    escalation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsEscalationOut:
    escalation = db.get(OpsEscalation, escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="escalation_not_found")
    _require_target_access(token, escalation.target)
    audit = AuditService(db)
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    updated = close_escalation(db, escalation=escalation, audit=audit, request_ctx=request_ctx)
    db.commit()
    db.refresh(updated)
    return OpsEscalationOut.model_validate(updated)


@router.post("/escalations/scan-sla", response_model=OpsEscalationScanResponse)
def admin_scan_sla_expiry(
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsEscalationScanResponse:
    _require_target_access(token, None)
    audit = AuditService(db)
    created = scan_explain_sla_expiry(
        db,
        tenant_id=_tenant_id_from_token(token),
        audit=audit,
    )
    db.commit()
    return OpsEscalationScanResponse(created=len(created))


__all__ = ["router"]

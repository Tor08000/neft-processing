from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.ops import OpsEscalation, OpsEscalationStatus, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.schemas.admin.ops import (
    OpsEscalationActionRequest,
    OpsEscalationListResponse,
    OpsEscalationOut,
    OpsEscalationScanResponse,
    OpsEscalationSLAReport,
    OpsKpiResponse,
)
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.ops.escalations import ack_escalation, close_escalation, list_escalations, scan_explain_sla_expiry
from app.services.ops.kpi import build_kpi_report
from app.services.ops.sla_reports import build_sla_report
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


def _actor_identifier(token: dict) -> str | None:
    return token.get("user_id") or token.get("sub") or token.get("email")


@router.get("/escalations", response_model=OpsEscalationListResponse)
def admin_list_escalations(
    target: OpsEscalationTarget | None = Query(None),
    status: OpsEscalationStatus | None = Query(None),
    primary_reason: PrimaryReason | None = Query(None),
    overdue: bool | None = Query(None),
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
        primary_reason=primary_reason,
        overdue=overdue,
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
    payload: OpsEscalationActionRequest,
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
    actor = actor_from_token(token)
    try:
        updated = ack_escalation(
            db,
            escalation=escalation,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor=_actor_identifier(token) or actor.user_id or actor.client_id,
            audit=audit,
            request_ctx=request_ctx,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(updated)
    return OpsEscalationOut.model_validate(updated)


@router.post("/escalations/{escalation_id}/close", response_model=OpsEscalationOut)
def admin_close_escalation(
    escalation_id: str,
    payload: OpsEscalationActionRequest,
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
    actor = actor_from_token(token)
    allow_from_open = actor.actor_type == "ADMIN"
    try:
        updated = close_escalation(
            db,
            escalation=escalation,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            actor=_actor_identifier(token) or actor.user_id or actor.client_id,
            allow_from_open=allow_from_open,
            audit=audit,
            request_ctx=request_ctx,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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


@router.get("/reports/sla", response_model=OpsEscalationSLAReport)
def admin_sla_report(
    period: date | None = Query(None),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsEscalationSLAReport:
    _require_target_access(token, None)
    report = build_sla_report(
        db,
        tenant_id=_tenant_id_from_token(token),
        period=period,
    )
    return OpsEscalationSLAReport.model_validate(report)


@router.get("/kpi", response_model=OpsKpiResponse)
def admin_ops_kpi(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OpsKpiResponse:
    _require_target_access(token, None)
    report = build_kpi_report(
        db,
        tenant_id=_tenant_id_from_token(token),
        date_from=date_from,
        date_to=date_to,
    )
    return OpsKpiResponse.model_validate(report)


__all__ = ["router"]

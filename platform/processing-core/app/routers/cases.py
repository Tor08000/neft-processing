from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.support import support_user_dep
from app.db import get_db
from app.models.cases import Case, CaseKind, CasePriority, CaseQueue, CaseSlaState, CaseStatus
from app.models.crm import CRMFeatureFlagType
from app.schemas.cases import (
    CaseCommentCreateRequest,
    CaseCommentOut,
    CaseCreateRequest,
    CaseDetailsResponse,
    CaseListResponse,
    CaseResponse,
    CaseSnapshotOut,
    CaseUpdateRequest,
)
from app.services import crm
from app.services.cases_service import (
    add_comment,
    create_case,
    get_case,
    list_case_comments,
    list_case_snapshots,
    list_cases,
    update_case,
)
from app.services.case_escalation_service import compute_sla_state
from app.services.support_cases import list_case_status_timeline, resolve_support_case_scope
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id

router = APIRouter(prefix="/cases", tags=["cases"])


def _tenant_id_from_token(db: Session, token: dict) -> int:
    default = DEFAULT_TENANT_ID if token.get("is_client") or token.get("is_partner") or token.get("is_admin") else None
    return resolve_token_tenant_id(
        token,
        db=db if token.get("is_client") else None,
        client_id=_client_scope_id(token) if token.get("is_client") else None,
        default=default,
        error_detail="missing_tenant_context",
    )


def _actor_identifier(token: dict) -> str | None:
    return token.get("user_id") or token.get("sub") or token.get("email")


def _client_scope_id(token: dict) -> str | None:
    raw = token.get("client_id") or token.get("org_id")
    return str(raw) if raw not in (None, "") else None


def _partner_scope_id(token: dict) -> str | None:
    raw = token.get("partner_id")
    return str(raw) if raw not in (None, "") else None


def _require_admin(token: dict) -> None:
    if not token.get("is_admin"):
        raise HTTPException(status_code=403, detail="forbidden")


def _parse_enum_list(raw: str | None, enum_cls):
    if not raw:
        return None
    values = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            values.append(enum_cls(item))
        except ValueError:
            try:
                values.append(enum_cls(item.split(".")[-1]))
            except Exception as exc:
                raise HTTPException(status_code=400, detail="invalid_filter") from exc
    return values or None


def _ensure_client_case_creation_enabled(db: Session, *, token: dict) -> None:
    client_id = _resolved_client_case_scope(db, token=token)
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    tenant_id = _tenant_id_from_token(db, token)
    flag = crm.repository.get_feature_flag(
        db,
        tenant_id=tenant_id,
        client_id=str(client_id),
        feature=CRMFeatureFlagType.CASES_ENABLED,
    )
    if flag is not None and not flag.enabled:
        raise HTTPException(status_code=403, detail="case_creation_disabled")


def _default_queue(kind: CaseKind, *, entity_type: str | None) -> CaseQueue | None:
    normalized = str(entity_type or "").strip().upper()
    if kind == CaseKind.DISPUTE or normalized in {"PAYOUT", "SETTLEMENT", "INVOICE"}:
        return CaseQueue.FINANCE_OPS
    if kind in {CaseKind.SUPPORT, CaseKind.ORDER, CaseKind.INCIDENT}:
        return CaseQueue.SUPPORT
    return None


def _resolved_client_case_scope(db: Session, *, token: dict) -> str | None:
    raw_client_id = _client_scope_id(token)
    if not raw_client_id:
        return None
    scope = resolve_support_case_scope(
        db,
        tenant_id=_tenant_id_from_token(db, token),
        client_id=str(token.get("client_id")) if token.get("client_id") else None,
        org_id=str(token.get("org_id")) if token.get("org_id") else None,
    )
    return scope.client_id or raw_client_id


def _get_case_with_marketplace_compat_tail(db: Session, *, tenant_id: int, case_id: str, token: dict):
    case = get_case(db, tenant_id=tenant_id, case_id=case_id)
    if case is not None or tenant_id == 0:
        return case
    if not (token.get("is_client") or token.get("is_partner")):
        return None
    return (
        db.query(Case)
        .filter(Case.id == case_id)
        .filter(Case.tenant_id == 0)
        .filter(Case.case_source_ref_type == "MARKETPLACE_ORDER")
        .one_or_none()
    )


@router.post("", response_model=CaseResponse, status_code=201)
def create_case_endpoint(
    payload: CaseCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseResponse:
    if token.get("is_client"):
        _ensure_client_case_creation_enabled(db, token=token)

    tenant_id = _tenant_id_from_token(db, token)
    actor = _actor_identifier(token)
    client_id = _resolved_client_case_scope(db, token=token) if token.get("is_client") else payload.client_id
    partner_id = _partner_scope_id(token) if token.get("is_partner") else payload.partner_id
    case = create_case(
        db,
        tenant_id=tenant_id,
        kind=payload.kind,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        kpi_key=payload.kpi_key,
        window_days=payload.window_days,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        note=payload.note,
        explain=payload.explain,
        diff=payload.diff,
        selected_actions=payload.selected_actions,
        mastery_snapshot=payload.mastery_snapshot,
        created_by=actor,
        client_id=client_id,
        partner_id=partner_id,
        queue=_default_queue(payload.kind, entity_type=payload.entity_type),
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    db.commit()
    db.refresh(case)
    case.sla_state = compute_sla_state(case)
    return CaseResponse.model_validate(case)


@router.get("", response_model=CaseListResponse)
def list_cases_endpoint(
    status: str | None = Query(None),
    kind: CaseKind | None = Query(None),
    priority: str | None = Query(None),
    queue: CaseQueue | None = Query(None),
    sla_state: CaseSlaState | None = Query(None),
    escalation_level_min: int | None = Query(None, ge=0),
    q: str | None = Query(None),
    assigned_to: str | None = Query(None),
    client_id: str | None = Query(None),
    partner_id: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseListResponse:
    tenant_id = _tenant_id_from_token(db, token)
    actor = _actor_identifier(token)
    if token.get("is_client") and not actor:
        raise HTTPException(status_code=403, detail="missing_actor_context")
    created_by = actor if token.get("is_client") else None
    resolved_client_id = _resolved_client_case_scope(db, token=token) if token.get("is_client") else client_id
    items, total, next_cursor = list_cases(
        db,
        tenant_id=tenant_id,
        created_by=created_by,
        client_id=resolved_client_id,
        include_unscoped_created_by=bool(token.get("is_client")),
        partner_id=_partner_scope_id(token) if token.get("is_partner") else partner_id,
        status=_parse_enum_list(status, CaseStatus),
        kind=kind,
        entity_type=entity_type,
        priority=_parse_enum_list(priority, CasePriority),
        queue=queue,
        sla_state=sla_state,
        escalation_level_min=escalation_level_min,
        q=q,
        limit=limit,
        cursor=cursor,
        assigned_to=assigned_to,
    )
    now = datetime.now(timezone.utc)
    for item in items:
        item.sla_state = compute_sla_state(item, now=now)
    return CaseListResponse(
        items=[CaseResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        next_cursor=next_cursor,
    )


@router.get("/{case_id}", response_model=CaseDetailsResponse)
def get_case_endpoint(
    case_id: str,
    include_snapshots: bool = Query(False),
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseDetailsResponse:
    tenant_id = _tenant_id_from_token(db, token)
    case = _get_case_with_marketplace_compat_tail(db, tenant_id=tenant_id, case_id=case_id, token=token)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    actor = _actor_identifier(token)
    if token.get("is_client") and not actor:
        raise HTTPException(status_code=403, detail="missing_actor_context")
    if token.get("is_client"):
        scoped_client_id = _resolved_client_case_scope(db, token=token)
        if case.client_id and scoped_client_id != case.client_id:
            raise HTTPException(status_code=404, detail="case_not_found")
        if case.client_id is None and case.created_by != actor:
            raise HTTPException(status_code=404, detail="case_not_found")
    if token.get("is_partner"):
        scoped_partner_id = _partner_scope_id(token)
        if case.partner_id != scoped_partner_id:
            raise HTTPException(status_code=404, detail="case_not_found")

    snapshots = list_case_snapshots(db, case_id=case_id, limit=None if include_snapshots else 1)
    latest_snapshot = snapshots[0] if snapshots else None
    comments = list_case_comments(db, case_id=case_id)
    case.sla_state = compute_sla_state(case)
    return CaseDetailsResponse(
        case=CaseResponse.model_validate(case),
        latest_snapshot=CaseSnapshotOut.model_validate(latest_snapshot) if latest_snapshot else None,
        comments=[CaseCommentOut.model_validate(item) for item in comments],
        timeline=[
            {"status": status_value, "occurred_at": occurred_at}
            for status_value, occurred_at in list_case_status_timeline(db, case_id=case_id)
        ],
        snapshots=[CaseSnapshotOut.model_validate(item) for item in snapshots] if include_snapshots else None,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case_endpoint(
    case_id: str,
    payload: CaseUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseResponse:
    _require_admin(token)
    tenant_id = _tenant_id_from_token(db, token)
    case = get_case(db, tenant_id=tenant_id, case_id=case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    actor = _actor_identifier(token)
    updated = update_case(
        db,
        case=case,
        status=payload.status,
        assigned_to=payload.assigned_to,
        priority=payload.priority,
        actor=actor,
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    db.commit()
    db.refresh(updated)
    updated.sla_state = compute_sla_state(updated)
    return CaseResponse.model_validate(updated)


@router.post("/{case_id}/comments", response_model=CaseCommentOut, status_code=201)
def add_case_comment_endpoint(
    case_id: str,
    payload: CaseCommentCreateRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseCommentOut:
    _require_admin(token)
    tenant_id = _tenant_id_from_token(db, token)
    case = get_case(db, tenant_id=tenant_id, case_id=case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    comment = add_comment(db, case=case, author=_actor_identifier(token), body=payload.body)
    db.commit()
    db.refresh(comment)
    return CaseCommentOut.model_validate(comment)


__all__ = ["router"]

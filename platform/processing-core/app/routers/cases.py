from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.support import support_user_dep
from app.db import get_db
from app.models.cases import CaseKind, CasePriority, CaseQueue, CaseSlaState, CaseStatus
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

router = APIRouter(prefix="/cases", tags=["cases"])


def _tenant_id_from_token(token: dict) -> int:
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant_context")
    return int(tenant_id)


def _actor_identifier(token: dict) -> str | None:
    return token.get("user_id") or token.get("sub") or token.get("email")


def _require_admin(token: dict) -> None:
    if not token.get("is_admin"):
        raise HTTPException(status_code=403, detail="forbidden")


def _reject_partner(token: dict) -> None:
    if token.get("is_partner"):
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
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    tenant_id = _tenant_id_from_token(token)
    flag = crm.repository.get_feature_flag(
        db,
        tenant_id=tenant_id,
        client_id=str(client_id),
        feature=CRMFeatureFlagType.CASES_ENABLED,
    )
    if flag is not None and not flag.enabled:
        raise HTTPException(status_code=403, detail="case_creation_disabled")


@router.post("", response_model=CaseResponse, status_code=201)
def create_case_endpoint(
    payload: CaseCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseResponse:
    _reject_partner(token)
    if token.get("is_client"):
        _ensure_client_case_creation_enabled(db, token=token)

    tenant_id = _tenant_id_from_token(token)
    actor = _actor_identifier(token)
    case = create_case(
        db,
        tenant_id=tenant_id,
        kind=payload.kind,
        entity_id=payload.entity_id,
        kpi_key=payload.kpi_key,
        window_days=payload.window_days,
        title=payload.title,
        priority=payload.priority,
        note=payload.note,
        explain=payload.explain,
        diff=payload.diff,
        selected_actions=payload.selected_actions,
        created_by=actor,
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
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
    token: dict = Depends(support_user_dep),
) -> CaseListResponse:
    _reject_partner(token)
    tenant_id = _tenant_id_from_token(token)
    actor = _actor_identifier(token)
    if token.get("is_client") and not actor:
        raise HTTPException(status_code=403, detail="missing_actor_context")
    created_by = actor if token.get("is_client") else None
    items, total, next_cursor = list_cases(
        db,
        tenant_id=tenant_id,
        created_by=created_by,
        status=_parse_enum_list(status, CaseStatus),
        kind=kind,
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
    _reject_partner(token)
    tenant_id = _tenant_id_from_token(token)
    case = get_case(db, tenant_id=tenant_id, case_id=case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    actor = _actor_identifier(token)
    if token.get("is_client") and not actor:
        raise HTTPException(status_code=403, detail="missing_actor_context")
    if token.get("is_client") and case.created_by != actor:
        raise HTTPException(status_code=404, detail="case_not_found")

    snapshots = list_case_snapshots(db, case_id=case_id, limit=None if include_snapshots else 1)
    latest_snapshot = snapshots[0] if snapshots else None
    comments = list_case_comments(db, case_id=case_id)
    case.sla_state = compute_sla_state(case)
    return CaseDetailsResponse(
        case=CaseResponse.model_validate(case),
        latest_snapshot=CaseSnapshotOut.model_validate(latest_snapshot) if latest_snapshot else None,
        comments=[CaseCommentOut.model_validate(item) for item in comments],
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
    _reject_partner(token)
    _require_admin(token)
    tenant_id = _tenant_id_from_token(token)
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
    _reject_partner(token)
    _require_admin(token)
    tenant_id = _tenant_id_from_token(token)
    case = get_case(db, tenant_id=tenant_id, case_id=case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    comment = add_comment(db, case=case, author=_actor_identifier(token), body=payload.body)
    db.commit()
    db.refresh(comment)
    return CaseCommentOut.model_validate(comment)


__all__ = ["router"]

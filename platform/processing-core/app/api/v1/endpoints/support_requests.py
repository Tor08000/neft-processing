from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.support import support_user_dep
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.cases import Case, CaseKind, CaseQueue, CaseStatus
from app.models.support_request import (
    SupportRequestPriority,
    SupportRequest,
    SupportRequestScopeType,
    SupportRequestStatus,
    SupportRequestSubjectType,
)
from app.schemas.support_requests import (
    SupportRequestCreate,
    SupportRequestDetail,
    SupportRequestListResponse,
    SupportRequestOut,
    SupportRequestStatusChange,
    SupportRequestTimelineEvent,
)
from app.services.audit_service import AuditService, request_context_from_request
from app.services.cases_service import get_case, update_case
from app.services.support_cases import (
    CASE_STATUS_TO_SUPPORT_REQUEST_STATUS,
    SUPPORT_REQUEST_STATUS_TO_CASE_STATUS,
    ensure_case_for_support_request,
    list_case_status_timeline,
    materialize_support_request_case,
    resolve_support_case_scope,
    serialize_case_as_support_request,
)
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id

router = APIRouter(prefix="/api/v1/support/requests", tags=["support-requests"])

SUPPORT_COMPAT_KINDS = {
    CaseKind.SUPPORT,
    CaseKind.ORDER,
    CaseKind.DISPUTE,
    CaseKind.INCIDENT,
}


def _resolve_scope(
    db: Session,
    token: dict,
) -> tuple[str, SupportRequestScopeType | None, str | None, str | None]:
    if token.get("is_admin"):
        return ("admin", None, None, None)
    if token.get("partner_id"):
        return ("partner", SupportRequestScopeType.PARTNER, None, str(token["partner_id"]))
    client_scope = resolve_support_case_scope(
        db,
        tenant_id=_resolve_tenant(token, db=db),
        client_id=str(token.get("client_id")) if token.get("client_id") else None,
        org_id=str(token.get("org_id")) if token.get("org_id") else None,
    )
    if client_scope.client_id:
        return ("client", SupportRequestScopeType.CLIENT, client_scope.client_id, None)
    raise HTTPException(status_code=403, detail="missing_scope_context")


def _resolve_tenant(token: dict, *, db: Session | None = None) -> int:
    default = DEFAULT_TENANT_ID if not token.get("is_admin") else None
    return resolve_token_tenant_id(
        token,
        db=db if token.get("client_id") else None,
        client_id=str(token.get("client_id")) if token.get("client_id") else None,
        default=default,
        error_detail="missing_tenant_context",
    )


def _actor_id(token: dict) -> str | None:
    return token.get("user_id") or token.get("sub") or token.get("email")


def _is_support_case(case: Case) -> bool:
    return (
        case.kind in SUPPORT_COMPAT_KINDS
        or case.queue == CaseQueue.SUPPORT
        or case.case_source_ref_type in {"SUPPORT_REQUEST", "SUPPORT_TICKET"}
    )


def _serialize_case(case: Case) -> SupportRequestOut:
    return SupportRequestOut(**serialize_case_as_support_request(case))


def _serialize_case_detail(
    db: Session,
    case: Case,
    *,
    correlation_id: str | None = None,
    event_id: str | None = None,
) -> SupportRequestDetail:
    payload = serialize_case_as_support_request(case)
    payload["correlation_id"] = correlation_id if correlation_id is not None else payload.get("correlation_id")
    payload["event_id"] = event_id if event_id is not None else payload.get("event_id")
    timeline = [
        SupportRequestTimelineEvent(
            status=CASE_STATUS_TO_SUPPORT_REQUEST_STATUS[status_value],
            occurred_at=occurred_at,
        )
        for status_value, occurred_at in list_case_status_timeline(db, case_id=str(case.id))
    ]
    return SupportRequestDetail(**payload, timeline=timeline)


def _load_legacy_support_request(
    db: Session,
    *,
    request_id: str,
) -> SupportRequest | None:
    return db.query(SupportRequest).filter(SupportRequest.id == request_id).one_or_none()


def _apply_scope_filters(
    query,
    *,
    role: str,
    scope_type: SupportRequestScopeType | None,
    resolved_client_id: str | None,
    resolved_partner_id: str | None,
    created_by: str | None,
    client_id: str | None,
    partner_id: str | None,
):
    if role == "admin":
        if client_id:
            query = query.filter(Case.client_id == client_id)
        if partner_id:
            query = query.filter(Case.partner_id == partner_id)
        return query
    if scope_type == SupportRequestScopeType.CLIENT:
        return query.filter(
            or_(
                Case.client_id == resolved_client_id,
                and_(Case.client_id.is_(None), Case.created_by == created_by),
            )
        )
    if scope_type == SupportRequestScopeType.PARTNER:
        return query.filter(Case.partner_id == resolved_partner_id)
    return query


def _materialize_legacy_requests(
    db: Session,
    *,
    role: str,
    scope_type: SupportRequestScopeType | None,
    resolved_client_id: str | None,
    resolved_partner_id: str | None,
    status: SupportRequestStatus | None,
    subject_type: SupportRequestSubjectType | None,
    date_from: date | None,
    date_to: date | None,
) -> None:
    query = db.query(SupportRequest)
    if role == "admin":
        if resolved_client_id:
            query = query.filter(SupportRequest.client_id == resolved_client_id)
        if resolved_partner_id:
            query = query.filter(SupportRequest.partner_id == resolved_partner_id)
    elif scope_type == SupportRequestScopeType.CLIENT:
        query = query.filter(SupportRequest.client_id == resolved_client_id)
    elif scope_type == SupportRequestScopeType.PARTNER:
        query = query.filter(SupportRequest.partner_id == resolved_partner_id)
    if status:
        query = query.filter(SupportRequest.status == status)
    if subject_type:
        query = query.filter(SupportRequest.subject_type == subject_type)
    if date_from:
        query = query.filter(SupportRequest.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        query = query.filter(SupportRequest.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))

    for support_request in query.all():
        materialize_support_request_case(db, support_request=support_request)
    db.flush()


def _sync_legacy_support_request(
    support_request: SupportRequest | None,
    *,
    status: SupportRequestStatus,
    now: datetime,
) -> None:
    if support_request is None:
        return
    support_request.status = status
    support_request.updated_at = now
    if status in {SupportRequestStatus.RESOLVED, SupportRequestStatus.CLOSED}:
        support_request.resolved_at = support_request.resolved_at or now


def _audit_support_request_event(
    db: Session,
    *,
    request: Request,
    token: dict,
    event_type: str,
    entity_id: str,
    action: str,
    visibility: AuditVisibility,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    AuditService(db).audit(
        event_type=event_type,
        entity_type="support_request",
        entity_id=entity_id,
        action=action,
        visibility=visibility,
        before=before,
        after=after,
        request_ctx=request_context_from_request(request, token=token),
    )


def _get_scoped_case_or_404(
    db: Session,
    *,
    request_id: str,
    tenant_id: int,
    role: str,
    scope_type: SupportRequestScopeType | None,
    resolved_client_id: str | None,
    resolved_partner_id: str | None,
    created_by: str | None,
) -> Case:
    case = get_case(db, tenant_id=tenant_id, case_id=request_id)
    if case is None:
        support_request = _load_legacy_support_request(db, request_id=request_id)
        if support_request is None:
            raise HTTPException(status_code=404, detail="support_request_not_found")
        case = materialize_support_request_case(db, support_request=support_request)
        db.flush()
    if not _is_support_case(case):
        raise HTTPException(status_code=404, detail="support_request_not_found")
    if role == "admin":
        return case
    if scope_type == SupportRequestScopeType.CLIENT:
        if case.client_id == resolved_client_id:
            return case
        if case.client_id is None and case.created_by == created_by:
            return case
        raise HTTPException(status_code=403, detail="forbidden")
    if scope_type == SupportRequestScopeType.PARTNER and case.partner_id != resolved_partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return case


@router.post("", response_model=SupportRequestDetail, status_code=201)
def create_support_request(
    request: Request,
    payload: SupportRequestCreate,
    token: dict = Depends(support_user_dep),
    db: Session = Depends(get_db),
) -> SupportRequestDetail:
    role, scope_type, client_id, partner_id = _resolve_scope(db, token)
    if role == "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    if payload.scope_type != scope_type:
        raise HTTPException(status_code=403, detail="forbidden_scope")
    if payload.subject_type != SupportRequestSubjectType.OTHER and not payload.subject_id:
        raise HTTPException(status_code=422, detail="subject_required")

    tenant_id = _resolve_tenant(token, db=db)
    actor_id = _actor_id(token)
    case_id = str(uuid4())
    case = ensure_case_for_support_request(
        db,
        support_request_id=case_id,
        scope_type=payload.scope_type,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        priority=SupportRequestPriority.NORMAL,
        status=SupportRequestStatus.OPEN,
        created_by_user_id=actor_id,
        tenant_id=tenant_id,
        client_id=client_id,
        partner_id=partner_id,
        request_ctx=request_context_from_request(request, token=token),
    )
    db.flush()
    _audit_support_request_event(
        db,
        request=request,
        token=token,
        event_type="SUPPORT_REQUEST_CREATED",
        entity_id=str(case.id),
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "status": SupportRequestStatus.OPEN.value,
            "scope_type": payload.scope_type.value,
            "subject_type": payload.subject_type.value,
            "subject_id": payload.subject_id,
            "case_id": str(case.id),
            "correlation_id": payload.correlation_id,
            "event_id": payload.event_id,
        },
    )
    db.commit()
    db.refresh(case)
    return _serialize_case_detail(
        db,
        case,
        correlation_id=payload.correlation_id,
        event_id=payload.event_id,
    )


@router.get("", response_model=SupportRequestListResponse)
def list_support_requests(
    token: dict = Depends(support_user_dep),
    db: Session = Depends(get_db),
    status: SupportRequestStatus | None = Query(default=None),
    subject_type: SupportRequestSubjectType | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    client_id: str | None = Query(default=None),
    partner_id: str | None = Query(default=None),
) -> SupportRequestListResponse:
    role, scope_type, resolved_client_id, resolved_partner_id = _resolve_scope(db, token)
    tenant_id = _resolve_tenant(token, db=db)
    created_by = _actor_id(token)
    admin_client_id = client_id if role == "admin" else resolved_client_id
    admin_partner_id = partner_id if role == "admin" else resolved_partner_id

    _materialize_legacy_requests(
        db,
        role=role,
        scope_type=scope_type,
        resolved_client_id=admin_client_id,
        resolved_partner_id=admin_partner_id,
        status=status,
        subject_type=subject_type,
        date_from=date_from,
        date_to=date_to,
    )

    query = db.query(Case).filter(Case.tenant_id == tenant_id)
    query = _apply_scope_filters(
        query,
        role=role,
        scope_type=scope_type,
        resolved_client_id=admin_client_id,
        resolved_partner_id=admin_partner_id,
        created_by=created_by,
        client_id=client_id,
        partner_id=partner_id,
    )
    query = query.filter(
        or_(
            Case.kind.in_(SUPPORT_COMPAT_KINDS),
            Case.queue == CaseQueue.SUPPORT,
            Case.case_source_ref_type.in_(["SUPPORT_REQUEST", "SUPPORT_TICKET"]),
        )
    )
    if status:
        query = query.filter(Case.status == SUPPORT_REQUEST_STATUS_TO_CASE_STATUS[status])
    if subject_type:
        query = query.filter(Case.entity_type == subject_type.value)
    if date_from:
        query = query.filter(Case.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        query = query.filter(Case.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))

    total = query.count()
    items = (
        query.order_by(Case.created_at.desc(), Case.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SupportRequestListResponse(
        items=[_serialize_case(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=SupportRequestDetail)
def get_support_request(
    request_id: str,
    token: dict = Depends(support_user_dep),
    db: Session = Depends(get_db),
) -> SupportRequestDetail:
    role, scope_type, resolved_client_id, resolved_partner_id = _resolve_scope(db, token)
    case = _get_scoped_case_or_404(
        db,
        request_id=request_id,
        tenant_id=_resolve_tenant(token, db=db),
        role=role,
        scope_type=scope_type,
        resolved_client_id=resolved_client_id,
        resolved_partner_id=resolved_partner_id,
        created_by=_actor_id(token),
    )
    return _serialize_case_detail(db, case)


@router.post("/{request_id}/status", response_model=SupportRequestDetail)
def update_support_request_status(
    request_id: str,
    payload: SupportRequestStatusChange,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> SupportRequestDetail:
    tenant_id = _resolve_tenant(token, db=db)
    case = _get_scoped_case_or_404(
        db,
        request_id=request_id,
        tenant_id=tenant_id,
        role="admin",
        scope_type=None,
        resolved_client_id=None,
        resolved_partner_id=None,
        created_by=None,
    )
    before_status = CASE_STATUS_TO_SUPPORT_REQUEST_STATUS[case.status]
    if before_status == payload.status:
        return _serialize_case_detail(db, case)

    now = datetime.now(timezone.utc)
    updated = update_case(
        db,
        case=case,
        status=SUPPORT_REQUEST_STATUS_TO_CASE_STATUS[payload.status],
        assigned_to=None,
        priority=None,
        actor=_actor_id(token),
        now=now,
        request_id=request.headers.get("x-request-id"),
        trace_id=request.headers.get("x-trace-id"),
    )
    legacy_row = _load_legacy_support_request(db, request_id=request_id)
    _sync_legacy_support_request(legacy_row, status=payload.status, now=now)
    _audit_support_request_event(
        db,
        request=request,
        token=token,
        event_type="SUPPORT_REQUEST_STATUS_CHANGED",
        entity_id=str(updated.id),
        action="STATUS_UPDATED",
        visibility=AuditVisibility.INTERNAL,
        before={"status": before_status.value},
        after={"status": payload.status.value},
    )
    if payload.status == SupportRequestStatus.RESOLVED:
        _audit_support_request_event(
            db,
            request=request,
            token=token,
            event_type="SUPPORT_REQUEST_RESOLVED",
            entity_id=str(updated.id),
            action="RESOLVED",
            visibility=AuditVisibility.INTERNAL,
            after={"status": payload.status.value},
        )
    if payload.status == SupportRequestStatus.CLOSED:
        _audit_support_request_event(
            db,
            request=request,
            token=token,
            event_type="SUPPORT_REQUEST_CLOSED",
            entity_id=str(updated.id),
            action="CLOSED",
            visibility=AuditVisibility.INTERNAL,
            after={"status": payload.status.value},
        )
    db.commit()
    db.refresh(updated)
    return _serialize_case_detail(db, updated)


__all__ = ["router"]

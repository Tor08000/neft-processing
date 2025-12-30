from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.support import support_user_dep
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.support_request import (
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

router = APIRouter(prefix="/api/v1/support/requests", tags=["support-requests"])


def _resolve_scope(token: dict) -> tuple[str, SupportRequestScopeType | None, str | None, str | None]:
    if token.get("is_admin"):
        return ("admin", None, None, None)
    if token.get("client_id"):
        return ("client", SupportRequestScopeType.CLIENT, str(token["client_id"]), None)
    if token.get("partner_id"):
        return ("partner", SupportRequestScopeType.PARTNER, None, str(token["partner_id"]))
    raise HTTPException(status_code=403, detail="missing_scope_context")


def _resolve_tenant(token: dict) -> int:
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant_context")
    return int(tenant_id)


def _serialize_request(item: SupportRequest) -> SupportRequestOut:
    return SupportRequestOut(
        id=str(item.id),
        tenant_id=item.tenant_id,
        client_id=item.client_id,
        partner_id=item.partner_id,
        created_by_user_id=item.created_by_user_id,
        scope_type=item.scope_type,
        subject_type=item.subject_type,
        subject_id=str(item.subject_id) if item.subject_id else None,
        correlation_id=item.correlation_id,
        event_id=str(item.event_id) if item.event_id else None,
        title=item.title,
        description=item.description,
        status=item.status,
        priority=item.priority,
        created_at=item.created_at,
        updated_at=item.updated_at,
        resolved_at=item.resolved_at,
    )


def _timeline_events(db: Session, support_request: SupportRequest) -> list[SupportRequestTimelineEvent]:
    from app.models.audit_log import AuditLog

    events = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "support_request")
        .filter(AuditLog.entity_id == str(support_request.id))
        .filter(AuditLog.event_type.in_(["SUPPORT_REQUEST_CREATED", "SUPPORT_REQUEST_STATUS_CHANGED", "SUPPORT_REQUEST_RESOLVED", "SUPPORT_REQUEST_CLOSED"]))
        .order_by(AuditLog.ts.asc())
        .all()
    )

    timeline: list[SupportRequestTimelineEvent] = []
    for entry in events:
        status_value = entry.after.get("status") if isinstance(entry.after, dict) else None
        if not status_value:
            if entry.event_type == "SUPPORT_REQUEST_CREATED":
                status_value = SupportRequestStatus.OPEN.value
            elif entry.event_type == "SUPPORT_REQUEST_RESOLVED":
                status_value = SupportRequestStatus.RESOLVED.value
            elif entry.event_type == "SUPPORT_REQUEST_CLOSED":
                status_value = SupportRequestStatus.CLOSED.value
        if status_value:
            timeline.append(
                SupportRequestTimelineEvent(
                    status=SupportRequestStatus(status_value),
                    occurred_at=entry.ts,
                )
            )
    return timeline


@router.post("", response_model=SupportRequestDetail, status_code=201)
def create_support_request(
    request: Request,
    payload: SupportRequestCreate,
    token: dict = Depends(support_user_dep),
    db: Session = Depends(get_db),
) -> SupportRequestDetail:
    role, scope_type, client_id, partner_id = _resolve_scope(token)
    if role == "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    if payload.scope_type != scope_type:
        raise HTTPException(status_code=403, detail="forbidden_scope")

    if payload.subject_type != SupportRequestSubjectType.OTHER and not payload.subject_id:
        raise HTTPException(status_code=422, detail="subject_required")

    tenant_id = _resolve_tenant(token)
    support_request = SupportRequest(
        tenant_id=tenant_id,
        client_id=client_id,
        partner_id=partner_id,
        created_by_user_id=token.get("user_id") or token.get("sub"),
        scope_type=payload.scope_type,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        correlation_id=payload.correlation_id,
        event_id=payload.event_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status=SupportRequestStatus.OPEN,
    )
    db.add(support_request)
    db.commit()
    db.refresh(support_request)

    audit_service = AuditService(db)
    request_ctx = request_context_from_request(request, token=token)
    audit_service.audit(
        event_type="SUPPORT_REQUEST_CREATED",
        entity_type="support_request",
        entity_id=str(support_request.id),
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "status": support_request.status.value,
            "scope_type": support_request.scope_type.value,
            "subject_type": support_request.subject_type.value,
            "subject_id": str(support_request.subject_id) if support_request.subject_id else None,
        },
        request_ctx=request_ctx,
    )

    return SupportRequestDetail(**_serialize_request(support_request).model_dump(), timeline=_timeline_events(db, support_request))


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
    role, scope_type, resolved_client_id, resolved_partner_id = _resolve_scope(token)

    query = db.query(SupportRequest)
    if role == "admin":
        if client_id:
            query = query.filter(SupportRequest.client_id == client_id)
        if partner_id:
            query = query.filter(SupportRequest.partner_id == partner_id)
        if scope_type:
            query = query.filter(SupportRequest.scope_type == scope_type)
    else:
        if scope_type == SupportRequestScopeType.CLIENT:
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

    total = query.count()
    items = (
        query.order_by(SupportRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return SupportRequestListResponse(
        items=[_serialize_request(item) for item in items],
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
    role, scope_type, resolved_client_id, resolved_partner_id = _resolve_scope(token)

    support_request = db.query(SupportRequest).filter(SupportRequest.id == request_id).one_or_none()
    if support_request is None:
        raise HTTPException(status_code=404, detail="support_request_not_found")

    if role != "admin":
        if scope_type != support_request.scope_type:
            raise HTTPException(status_code=403, detail="forbidden_scope")
        if scope_type == SupportRequestScopeType.CLIENT and support_request.client_id != resolved_client_id:
            raise HTTPException(status_code=403, detail="forbidden")
        if scope_type == SupportRequestScopeType.PARTNER and support_request.partner_id != resolved_partner_id:
            raise HTTPException(status_code=403, detail="forbidden")

    return SupportRequestDetail(**_serialize_request(support_request).model_dump(), timeline=_timeline_events(db, support_request))


@router.post("/{request_id}/status", response_model=SupportRequestDetail)
def update_support_request_status(
    request_id: str,
    payload: SupportRequestStatusChange,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> SupportRequestDetail:
    support_request = db.query(SupportRequest).filter(SupportRequest.id == request_id).one_or_none()
    if support_request is None:
        raise HTTPException(status_code=404, detail="support_request_not_found")

    before_status = support_request.status
    if before_status == payload.status:
        return SupportRequestDetail(**_serialize_request(support_request).model_dump(), timeline=_timeline_events(db, support_request))

    support_request.status = payload.status
    if payload.status in {SupportRequestStatus.RESOLVED, SupportRequestStatus.CLOSED}:
        support_request.resolved_at = support_request.resolved_at or datetime.now(timezone.utc)

    db.add(support_request)
    db.commit()
    db.refresh(support_request)

    audit_service = AuditService(db)
    request_ctx = request_context_from_request(request, token=token)
    audit_service.audit(
        event_type="SUPPORT_REQUEST_STATUS_CHANGED",
        entity_type="support_request",
        entity_id=str(support_request.id),
        action="STATUS_UPDATED",
        visibility=AuditVisibility.INTERNAL,
        before={"status": before_status.value},
        after={"status": support_request.status.value},
        request_ctx=request_ctx,
    )

    if payload.status == SupportRequestStatus.RESOLVED:
        audit_service.audit(
            event_type="SUPPORT_REQUEST_RESOLVED",
            entity_type="support_request",
            entity_id=str(support_request.id),
            action="RESOLVED",
            visibility=AuditVisibility.INTERNAL,
            after={"status": support_request.status.value},
            request_ctx=request_ctx,
        )
    if payload.status == SupportRequestStatus.CLOSED:
        audit_service.audit(
            event_type="SUPPORT_REQUEST_CLOSED",
            entity_type="support_request",
            entity_id=str(support_request.id),
            action="CLOSED",
            visibility=AuditVisibility.INTERNAL,
            after={"status": support_request.status.value},
            request_ctx=request_ctx,
        )

    return SupportRequestDetail(**_serialize_request(support_request).model_dump(), timeline=_timeline_events(db, support_request))


__all__ = ["router"]

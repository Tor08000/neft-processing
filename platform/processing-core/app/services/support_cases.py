from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType
from app.models.cases import (
    Case,
    CaseComment,
    CaseCommentType,
    CaseEventType,
    CaseKind,
    CasePriority,
    CaseQueue,
    CaseStatus,
)
from app.models.crm import CRMClient
from app.models.support_request import (
    SupportRequest,
    SupportRequestPriority,
    SupportRequestScopeType,
    SupportRequestStatus,
    SupportRequestSubjectType,
)
from app.models.support_ticket import SupportTicket, SupportTicketPriority, SupportTicketStatus
from app.services.audit_service import RequestContext
from app.services.case_events_service import list_case_events
from app.services.cases_service import add_comment, close_case, create_case, update_case


SUPPORT_REQUEST_STATUS_TO_CASE_STATUS = {
    SupportRequestStatus.OPEN: CaseStatus.TRIAGE,
    SupportRequestStatus.IN_PROGRESS: CaseStatus.IN_PROGRESS,
    SupportRequestStatus.WAITING: CaseStatus.WAITING,
    SupportRequestStatus.RESOLVED: CaseStatus.RESOLVED,
    SupportRequestStatus.CLOSED: CaseStatus.CLOSED,
}

CASE_STATUS_TO_SUPPORT_REQUEST_STATUS = {
    CaseStatus.TRIAGE: SupportRequestStatus.OPEN,
    CaseStatus.IN_PROGRESS: SupportRequestStatus.IN_PROGRESS,
    CaseStatus.WAITING: SupportRequestStatus.WAITING,
    CaseStatus.RESOLVED: SupportRequestStatus.RESOLVED,
    CaseStatus.CLOSED: SupportRequestStatus.CLOSED,
}

SUPPORT_TICKET_STATUS_TO_CASE_STATUS = {
    SupportTicketStatus.OPEN: CaseStatus.TRIAGE,
    SupportTicketStatus.IN_PROGRESS: CaseStatus.IN_PROGRESS,
    SupportTicketStatus.CLOSED: CaseStatus.CLOSED,
}

CASE_STATUS_TO_SUPPORT_TICKET_STATUS = {
    CaseStatus.TRIAGE: SupportTicketStatus.OPEN,
    CaseStatus.IN_PROGRESS: SupportTicketStatus.IN_PROGRESS,
    CaseStatus.WAITING: SupportTicketStatus.IN_PROGRESS,
    CaseStatus.RESOLVED: SupportTicketStatus.IN_PROGRESS,
    CaseStatus.CLOSED: SupportTicketStatus.CLOSED,
}

SUPPORT_REQUEST_PRIORITY_TO_CASE_PRIORITY = {
    SupportRequestPriority.LOW: CasePriority.LOW,
    SupportRequestPriority.NORMAL: CasePriority.MEDIUM,
    SupportRequestPriority.HIGH: CasePriority.HIGH,
}

CASE_PRIORITY_TO_SUPPORT_REQUEST_PRIORITY = {
    CasePriority.LOW: SupportRequestPriority.LOW,
    CasePriority.MEDIUM: SupportRequestPriority.NORMAL,
    CasePriority.HIGH: SupportRequestPriority.HIGH,
    CasePriority.CRITICAL: SupportRequestPriority.HIGH,
}

SUPPORT_TICKET_PRIORITY_TO_CASE_PRIORITY = {
    SupportTicketPriority.LOW: CasePriority.LOW,
    SupportTicketPriority.NORMAL: CasePriority.MEDIUM,
    SupportTicketPriority.HIGH: CasePriority.HIGH,
}

CASE_PRIORITY_TO_SUPPORT_TICKET_PRIORITY = {
    CasePriority.LOW: SupportTicketPriority.LOW,
    CasePriority.MEDIUM: SupportTicketPriority.NORMAL,
    CasePriority.HIGH: SupportTicketPriority.HIGH,
    CasePriority.CRITICAL: SupportTicketPriority.HIGH,
}


@dataclass(frozen=True)
class SupportCaseScope:
    tenant_id: int | None
    client_id: str | None
    partner_id: str | None


@dataclass(frozen=True)
class SupportTicketCaseSummary:
    case_id: str
    status: CaseStatus
    queue: CaseQueue
    priority: CasePriority
    updated_at: datetime


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        return inspect(db.get_bind()).has_table(name)
    except Exception:
        return False


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind())


def _column_exists(table: Table, name: str) -> bool:
    return name in table.c


def _resolve_client_id_from_org(db: Session, *, org_id: str | None) -> str | None:
    if not org_id:
        return None
    candidate = str(org_id).strip()
    if not candidate:
        return None
    crm_client = db.query(CRMClient).filter(CRMClient.id == candidate).one_or_none()
    if crm_client is not None:
        return str(crm_client.id)
    if not _table_exists(db, "orgs"):
        return None
    try:
        orgs = _table(db, "orgs")
    except Exception:
        return None
    if not _column_exists(orgs, "id"):
        return None
    client_col = orgs.c.client_id if _column_exists(orgs, "client_id") else None
    if client_col is None and _column_exists(orgs, "client_uuid"):
        client_col = orgs.c.client_uuid
    if client_col is None:
        return None
    try:
        record = db.execute(select(client_col).where(orgs.c.id == int(candidate))).scalar_one_or_none()
    except Exception:
        return None
    if record is None:
        return None
    return str(record)


def resolve_support_case_scope(
    db: Session,
    *,
    tenant_id: int | None = None,
    client_id: str | None = None,
    partner_id: str | None = None,
    org_id: str | None = None,
) -> SupportCaseScope:
    resolved_client_id = str(client_id).strip() if client_id else None
    if not resolved_client_id:
        resolved_client_id = _resolve_client_id_from_org(db, org_id=org_id)
    resolved_partner_id = str(partner_id).strip() if partner_id else None
    resolved_tenant_id = tenant_id
    if resolved_tenant_id is None and resolved_client_id:
        client = db.query(CRMClient).filter(CRMClient.id == resolved_client_id).one_or_none()
        if client is not None:
            resolved_tenant_id = int(client.tenant_id)
    return SupportCaseScope(
        tenant_id=resolved_tenant_id,
        client_id=resolved_client_id or (str(org_id).strip() if org_id else None),
        partner_id=resolved_partner_id,
    )


def support_request_subject_to_case_kind(subject_type: SupportRequestSubjectType) -> CaseKind:
    if subject_type == SupportRequestSubjectType.ORDER:
        return CaseKind.ORDER
    if subject_type in {SupportRequestSubjectType.PAYOUT, SupportRequestSubjectType.SETTLEMENT}:
        return CaseKind.DISPUTE
    if subject_type == SupportRequestSubjectType.DOCUMENT:
        return CaseKind.INCIDENT
    return CaseKind.SUPPORT


def support_request_subject_to_case_queue(subject_type: SupportRequestSubjectType) -> CaseQueue:
    if subject_type in {SupportRequestSubjectType.PAYOUT, SupportRequestSubjectType.SETTLEMENT}:
        return CaseQueue.FINANCE_OPS
    return CaseQueue.SUPPORT


def case_to_support_request_subject(
    *,
    kind: CaseKind,
    entity_type: str | None,
) -> SupportRequestSubjectType:
    normalized = str(entity_type or "").strip().upper()
    if normalized in {item.value for item in SupportRequestSubjectType}:
        return SupportRequestSubjectType(normalized)
    if kind == CaseKind.ORDER:
        return SupportRequestSubjectType.ORDER
    if kind == CaseKind.DISPUTE:
        return SupportRequestSubjectType.PAYOUT
    if kind == CaseKind.INCIDENT:
        return SupportRequestSubjectType.DOCUMENT
    return SupportRequestSubjectType.OTHER


def list_case_status_timeline(db: Session, *, case_id: str) -> list[tuple[CaseStatus, datetime]]:
    timeline: list[tuple[CaseStatus, datetime]] = []
    for event in list_case_events(db, case_id=case_id, limit=500):
        payload = event.payload_redacted or {}
        changes = payload.get("changes") or []
        created_status: CaseStatus | None = None
        for change in changes:
            if change.get("field") != "status":
                continue
            after = change.get("to")
            if not after:
                continue
            try:
                status_value = CaseStatus(after)
            except ValueError:
                continue
            if event.type == CaseEventType.CASE_CREATED and created_status is None:
                created_status = status_value
            else:
                timeline.append((status_value, event.at))
        if event.type == CaseEventType.CASE_CREATED:
            timeline.append((created_status or CaseStatus.TRIAGE, event.at))
    return timeline


def ensure_case_for_support_request(
    db: Session,
    *,
    support_request_id: str,
    scope_type: SupportRequestScopeType,
    subject_type: SupportRequestSubjectType,
    subject_id: str | None,
    title: str,
    description: str,
    priority: SupportRequestPriority,
    status: SupportRequestStatus,
    created_by_user_id: str | None,
    tenant_id: int | None,
    client_id: str | None,
    partner_id: str | None,
    occurred_at: datetime | None = None,
    request_ctx: RequestContext | None = None,
) -> Case:
    scope = resolve_support_case_scope(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        partner_id=partner_id if scope_type == SupportRequestScopeType.PARTNER else None,
        org_id=client_id if scope_type == SupportRequestScopeType.CLIENT else None,
    )
    if scope.tenant_id is None:
        raise ValueError("support_case_tenant_unresolved")
    existing = (
        db.query(Case)
        .filter(Case.id == support_request_id)
        .filter(Case.tenant_id == scope.tenant_id)
        .one_or_none()
    )
    if existing is not None:
        return existing
    return create_case(
        db,
        case_id=support_request_id,
        tenant_id=scope.tenant_id,
        kind=support_request_subject_to_case_kind(subject_type),
        entity_type=subject_type.value,
        entity_id=subject_id,
        kpi_key=None,
        window_days=None,
        title=title,
        description=description,
        priority=SUPPORT_REQUEST_PRIORITY_TO_CASE_PRIORITY[priority],
        status=SUPPORT_REQUEST_STATUS_TO_CASE_STATUS[status],
        note=description,
        explain={"compatibility_surface": "support_requests_v1"},
        diff=None,
        selected_actions=None,
        mastery_snapshot=None,
        created_by=created_by_user_id,
        client_id=scope.client_id if scope_type == SupportRequestScopeType.CLIENT else None,
        partner_id=scope.partner_id if scope_type == SupportRequestScopeType.PARTNER else None,
        case_source_ref_type="SUPPORT_REQUEST",
        case_source_ref_id=support_request_id,
        queue=support_request_subject_to_case_queue(subject_type),
        occurred_at=occurred_at or datetime.now(timezone.utc),
        request_id=request_ctx.request_id if request_ctx else None,
        trace_id=request_ctx.trace_id if request_ctx else None,
    )


def materialize_support_request_case(
    db: Session,
    *,
    support_request: SupportRequest,
    request_ctx: RequestContext | None = None,
) -> Case:
    return ensure_case_for_support_request(
        db,
        support_request_id=str(support_request.id),
        scope_type=support_request.scope_type,
        subject_type=support_request.subject_type,
        subject_id=str(support_request.subject_id) if support_request.subject_id else None,
        title=support_request.title,
        description=support_request.description,
        priority=support_request.priority,
        status=support_request.status,
        created_by_user_id=support_request.created_by_user_id,
        tenant_id=support_request.tenant_id,
        client_id=support_request.client_id,
        partner_id=support_request.partner_id,
        occurred_at=support_request.created_at,
        request_ctx=request_ctx,
    )


def serialize_case_as_support_request(case: Case) -> dict[str, object]:
    scope_type = (
        SupportRequestScopeType.PARTNER if case.partner_id else SupportRequestScopeType.CLIENT
    )
    subject_type = case_to_support_request_subject(kind=case.kind, entity_type=case.entity_type)
    resolved_at = case.updated_at if case.status in {CaseStatus.RESOLVED, CaseStatus.CLOSED} else None
    return {
        "id": str(case.id),
        "tenant_id": case.tenant_id,
        "client_id": case.client_id,
        "partner_id": case.partner_id,
        "created_by_user_id": case.created_by,
        "scope_type": scope_type,
        "subject_type": subject_type,
        "subject_id": case.entity_id,
        "correlation_id": None,
        "event_id": None,
        "title": case.title,
        "description": case.description or "",
        "status": CASE_STATUS_TO_SUPPORT_REQUEST_STATUS[case.status],
        "priority": CASE_PRIORITY_TO_SUPPORT_REQUEST_PRIORITY[case.priority],
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "resolved_at": resolved_at,
    }


def get_support_ticket_case(db: Session, *, ticket_id: str) -> Case | None:
    return db.query(Case).filter(Case.id == ticket_id).one_or_none()


def summarize_support_ticket_case(case: Case | None) -> SupportTicketCaseSummary | None:
    if case is None:
        return None
    return SupportTicketCaseSummary(
        case_id=str(case.id),
        status=case.status,
        queue=case.queue,
        priority=case.priority,
        updated_at=case.updated_at,
    )


def sync_support_ticket_case(
    db: Session,
    *,
    ticket: SupportTicket,
    tenant_id: int | None = None,
    client_id: str | None = None,
    partner_id: str | None = None,
    actor_id: str | None = None,
    actor_email: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    kind: CaseKind = CaseKind.SUPPORT,
    entity_type: str = "SUPPORT_TICKET",
    entity_id: str | None = None,
    queue: CaseQueue | None = None,
) -> Case | None:
    case = get_support_ticket_case(db, ticket_id=str(ticket.id))
    scope = resolve_support_case_scope(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        partner_id=partner_id,
        org_id=str(ticket.org_id),
    )
    if scope.tenant_id is None and case is None:
        return None
    if case is None:
        return create_case(
            db,
            case_id=str(ticket.id),
            tenant_id=scope.tenant_id,
            kind=kind,
            entity_type=entity_type,
            entity_id=entity_id or str(ticket.id),
            kpi_key=None,
            window_days=None,
            title=ticket.subject,
            description=ticket.message,
            priority=SUPPORT_TICKET_PRIORITY_TO_CASE_PRIORITY[ticket.priority],
            status=SUPPORT_TICKET_STATUS_TO_CASE_STATUS[ticket.status],
            note=ticket.message,
            explain={"support_ticket_id": str(ticket.id), "org_id": str(ticket.org_id)},
            diff=None,
            selected_actions=None,
            mastery_snapshot=None,
            created_by=str(ticket.created_by_user_id),
            client_id=scope.client_id,
            partner_id=scope.partner_id,
            case_source_ref_type="SUPPORT_TICKET",
            case_source_ref_id=str(ticket.id),
            queue=queue or CaseQueue.SUPPORT,
            occurred_at=ticket.created_at,
            request_id=request_id,
            trace_id=trace_id,
        )

    updated = False
    if case.title != ticket.subject:
        case.title = ticket.subject
        updated = True
    if case.description != ticket.message:
        case.description = ticket.message
        updated = True
    desired_priority = SUPPORT_TICKET_PRIORITY_TO_CASE_PRIORITY[ticket.priority]
    if case.priority != desired_priority:
        case.priority = desired_priority
        updated = True
    if scope.client_id and case.client_id != scope.client_id:
        case.client_id = scope.client_id
        updated = True
    if scope.partner_id and case.partner_id != scope.partner_id:
        case.partner_id = scope.partner_id
        updated = True
    if case.entity_type != entity_type:
        case.entity_type = entity_type
        updated = True
    if case.entity_id != (entity_id or str(ticket.id)):
        case.entity_id = entity_id or str(ticket.id)
        updated = True
    if case.case_source_ref_type != "SUPPORT_TICKET":
        case.case_source_ref_type = "SUPPORT_TICKET"
        updated = True
    if str(case.case_source_ref_id or "") != str(ticket.id):
        case.case_source_ref_id = str(ticket.id)
        updated = True
    if queue and case.queue != queue:
        case.queue = queue
        updated = True

    desired_status = SUPPORT_TICKET_STATUS_TO_CASE_STATUS[ticket.status]
    if case.status != desired_status and case.status != CaseStatus.CLOSED:
        if desired_status == CaseStatus.CLOSED:
            close_case(
                db,
                case=case,
                actor=actor_id or str(ticket.created_by_user_id),
                resolution_note=ticket.subject,
                score_snapshot=None,
                mastery_snapshot=None,
                now=ticket.resolved_at or ticket.updated_at,
                request_id=request_id,
                trace_id=trace_id,
            )
        else:
            update_case(
                db,
                case=case,
                status=desired_status,
                assigned_to=None,
                priority=None,
                actor=actor_id or str(ticket.created_by_user_id),
                now=ticket.updated_at,
                request_id=request_id,
                trace_id=trace_id,
            )
    elif updated:
        case.updated_at = ticket.updated_at
        case.last_activity_at = ticket.updated_at
    return case


def sync_support_ticket_comment(
    db: Session,
    *,
    ticket: SupportTicket,
    author: str | None,
    body: str,
    occurred_at: datetime | None,
    comment_type: CaseCommentType = CaseCommentType.USER,
) -> CaseComment | None:
    case = get_support_ticket_case(db, ticket_id=str(ticket.id))
    if case is None:
        return None
    existing = (
        db.query(CaseComment)
        .filter(CaseComment.case_id == case.id)
        .filter(CaseComment.author == author)
        .filter(CaseComment.body == body)
        .filter(CaseComment.created_at == occurred_at)
        .one_or_none()
    )
    if existing is not None:
        return existing
    return add_comment(
        db,
        case=case,
        author=author,
        body=body,
        comment_type=comment_type,
        now=occurred_at,
    )


def request_context_from_support_token(token: dict) -> RequestContext:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role and role not in roles:
        roles.append(role)
    return RequestContext(
        actor_type=ActorType.USER,
        actor_id=token.get("user_id") or token.get("sub") or token.get("email"),
        actor_email=token.get("email"),
        actor_roles=[str(item) for item in roles] if roles else None,
        request_id=None,
        trace_id=None,
        tenant_id=token.get("tenant_id"),
    )


__all__ = [
    "CASE_PRIORITY_TO_SUPPORT_REQUEST_PRIORITY",
    "CASE_PRIORITY_TO_SUPPORT_TICKET_PRIORITY",
    "CASE_STATUS_TO_SUPPORT_REQUEST_STATUS",
    "CASE_STATUS_TO_SUPPORT_TICKET_STATUS",
    "SUPPORT_REQUEST_PRIORITY_TO_CASE_PRIORITY",
    "SUPPORT_REQUEST_STATUS_TO_CASE_STATUS",
    "SUPPORT_TICKET_PRIORITY_TO_CASE_PRIORITY",
    "SUPPORT_TICKET_STATUS_TO_CASE_STATUS",
    "SupportCaseScope",
    "SupportTicketCaseSummary",
    "case_to_support_request_subject",
    "ensure_case_for_support_request",
    "get_support_ticket_case",
    "list_case_status_timeline",
    "materialize_support_request_case",
    "request_context_from_support_token",
    "resolve_support_case_scope",
    "serialize_case_as_support_request",
    "summarize_support_ticket_case",
    "support_request_subject_to_case_kind",
    "support_request_subject_to_case_queue",
    "sync_support_ticket_case",
    "sync_support_ticket_comment",
]

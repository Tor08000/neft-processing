from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.cases import (
    Case,
    CaseComment,
    CaseCommentType,
    CaseEventType,
    CaseKind,
    CasePriority,
    CaseQueue,
    CaseSlaState,
    CaseSnapshot,
    CaseStatus,
)
from app.services.case_events_service import CaseEventActor, CaseEventChange, emit_case_event
from app.services.case_escalation_service import apply_classification, apply_sla_filter, classify_case
from app.services.decision_memory.records import _extract_score_snapshot, record_decision_memory
from app.services.cases_metrics import metrics as case_metrics


def _format_score(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric > 1:
        numeric = numeric / 100.0
    return f"{numeric:.2f}"


def _build_case_title(
    *,
    kind: CaseKind,
    entity_id: str | None,
    kpi_key: str | None,
    explain: dict[str, Any] | None,
    diff: dict[str, Any] | None,
) -> str:
    target = entity_id or kpi_key or "unknown"
    prefix = f"Case: {kind.value} {target}"
    decision_label: str | None = None
    score_label: str | None = None

    if diff:
        decision_diff = diff.get("decision_diff") if isinstance(diff, dict) else None
        if isinstance(decision_diff, dict):
            before = decision_diff.get("before")
            after = decision_diff.get("after")
            if before and after and before != after:
                decision_label = f"{before} → {after}"
            else:
                decision_label = after or before
        score_diff = diff.get("score_diff") if isinstance(diff, dict) else None
        if isinstance(score_diff, dict):
            before_score = _format_score(score_diff.get("risk_before"))
            after_score = _format_score(score_diff.get("risk_after"))
            if before_score and after_score:
                score_label = f"{before_score} → {after_score}"

    if not decision_label and explain and isinstance(explain, dict):
        decision_label = explain.get("decision")
    if not score_label and explain and isinstance(explain, dict):
        score_label = _format_score(explain.get("score"))

    if decision_label and score_label:
        title = f"{prefix} — {decision_label} {score_label}"
    elif decision_label:
        title = f"{prefix} — {decision_label}"
    elif score_label:
        title = f"{prefix} — {score_label}"
    else:
        title = prefix

    if len(title) > 160:
        return f"{title[:157]}..."
    return title


def create_case(
    db: Session,
    *,
    case_id: str | None = None,
    tenant_id: int,
    kind: CaseKind,
    entity_type: str | None,
    entity_id: str | None,
    kpi_key: str | None,
    window_days: int | None,
    title: str | None,
    description: str | None,
    priority: CasePriority,
    status: CaseStatus = CaseStatus.TRIAGE,
    note: str | None,
    explain: dict[str, Any] | None,
    diff: dict[str, Any] | None,
    selected_actions: list[dict[str, Any]] | None,
    mastery_snapshot: dict[str, Any] | None,
    created_by: str | None,
    client_id: str | None = None,
    partner_id: str | None = None,
    case_source_ref_type: str | None = None,
    case_source_ref_id: str | None = None,
    queue: CaseQueue | None = None,
    occurred_at: datetime | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> Case:
    now = occurred_at or datetime.now(timezone.utc)
    resolved_title = title or _build_case_title(
        kind=kind,
        entity_id=entity_id,
        kpi_key=kpi_key,
        explain=explain,
        diff=diff,
    )
    case = Case(
        id=case_id,
        tenant_id=tenant_id,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        kpi_key=kpi_key,
        window_days=window_days,
        title=resolved_title,
        description=description,
        status=status,
        queue=queue or CaseQueue.GENERAL,
        priority=priority,
        client_id=client_id,
        partner_id=partner_id,
        created_by=created_by,
        case_source_ref_type=case_source_ref_type,
        case_source_ref_id=case_source_ref_id,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )
    db.add(case)
    db.flush()

    snapshot = CaseSnapshot(
        case_id=case.id,
        explain_snapshot=explain or {},
        diff_snapshot=diff,
        selected_actions=selected_actions,
        note=note or description,
        created_at=now,
    )
    db.add(snapshot)
    db.add(
        CaseComment(
            case_id=case.id,
            author=created_by,
            type=CaseCommentType.SYSTEM,
            body="Кейс создан",
            created_at=now,
        )
    )
    db.flush()
    classification = classify_case(case, explain, diff)
    apply_classification(db, case=case, result=classification, now=now)
    if case.queue == CaseQueue.SUPPORT:
        case_metrics.mark_support_ticket_created(case.priority.value)
    event = emit_case_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.CASE_CREATED,
        actor=CaseEventActor(id=created_by, email=None) if created_by else None,
        request_id=request_id,
        trace_id=trace_id,
        changes=[
            CaseEventChange(field="status", before=None, after=case.status.value),
            CaseEventChange(field="priority", before=None, after=case.priority.value),
            CaseEventChange(field="queue", before=None, after=case.queue.value),
            CaseEventChange(field="entity_type", before=None, after=entity_type),
            CaseEventChange(field="entity_id", before=None, after=entity_id),
        ]
        + (
            [CaseEventChange(field="note", before=None, after=note)]
            if note is not None
            else []
        ),
        at=now,
    )
    record_decision_memory(
        db,
        case_id=case.id,
        decision_type="action",
        decision_ref_id=event.id,
        decision_at=now,
        decided_by_user_id=created_by,
        context_snapshot={
            "case_id": str(case.id),
            "status": case.status.value,
            "priority": case.priority.value,
            "queue": case.queue.value,
        },
        rationale=note,
        score_snapshot=_extract_score_snapshot(explain),
        mastery_snapshot=mastery_snapshot,
        audit_event_id=event.id,
    )
    if explain:
        record_decision_memory(
            db,
            case_id=case.id,
            decision_type="explain",
            decision_ref_id=snapshot.id,
            decision_at=now,
            decided_by_user_id=created_by,
            context_snapshot=explain,
            rationale=None,
            score_snapshot=_extract_score_snapshot(explain),
            mastery_snapshot=mastery_snapshot,
            audit_event_id=event.id,
        )
    if diff:
        record_decision_memory(
            db,
            case_id=case.id,
            decision_type="diff",
            decision_ref_id=snapshot.id,
            decision_at=now,
            decided_by_user_id=created_by,
            context_snapshot=diff,
            rationale=None,
            score_snapshot=_extract_score_snapshot(diff),
            mastery_snapshot=mastery_snapshot,
            audit_event_id=event.id,
        )
    return case


def list_cases(
    db: Session,
    *,
    tenant_id: int,
    created_by: str | None = None,
    client_id: str | None = None,
    include_unscoped_created_by: bool = False,
    partner_id: str | None = None,
    status: list[CaseStatus] | None = None,
    kind: CaseKind | None = None,
    entity_type: str | None = None,
    priority: list[CasePriority] | None = None,
    queue: CaseQueue | None = None,
    sla_state: CaseSlaState | None = None,
    escalation_level_min: int | None = None,
    q: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    assigned_to: str | None = None,
) -> tuple[list[Case], int, str | None]:
    query = db.query(Case).filter(Case.tenant_id == tenant_id)
    if client_id and created_by and include_unscoped_created_by:
        query = query.filter(
            or_(
                Case.client_id == client_id,
                and_(Case.client_id.is_(None), Case.created_by == created_by),
            )
        )
    elif client_id:
        query = query.filter(Case.client_id == client_id)
    elif created_by:
        query = query.filter(Case.created_by == created_by)
    if partner_id:
        query = query.filter(Case.partner_id == partner_id)
    if status:
        query = query.filter(Case.status.in_(status))
    if kind:
        query = query.filter(Case.kind == kind)
    if entity_type:
        query = query.filter(Case.entity_type == entity_type)
    if priority:
        query = query.filter(Case.priority.in_(priority))
    if queue:
        query = query.filter(Case.queue == queue)
    if escalation_level_min is not None:
        query = query.filter(Case.escalation_level >= escalation_level_min)
    if assigned_to:
        query = query.filter(Case.assigned_to == assigned_to)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Case.title.ilike(pattern),
                Case.description.ilike(pattern),
                Case.entity_type.ilike(pattern),
                Case.entity_id.ilike(pattern),
                Case.kpi_key.ilike(pattern),
            )
        )
    if sla_state:
        query = apply_sla_filter(query, sla_state=sla_state, now=datetime.now(timezone.utc))

    total = query.count()
    offset = int(cursor or 0)
    items = (
        query.order_by(Case.last_activity_at.desc(), Case.id.desc())
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = str(offset + limit)
    return items, total, next_cursor


def get_case(db: Session, *, tenant_id: int, case_id: str) -> Case | None:
    return (
        db.query(Case)
        .filter(Case.tenant_id == tenant_id)
        .filter(Case.id == case_id)
        .one_or_none()
    )


def list_case_snapshots(db: Session, *, case_id: str, limit: int | None = None) -> list[CaseSnapshot]:
    query = db.query(CaseSnapshot).filter(CaseSnapshot.case_id == case_id).order_by(CaseSnapshot.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def list_case_comments(db: Session, *, case_id: str) -> list[CaseComment]:
    return (
        db.query(CaseComment)
        .filter(CaseComment.case_id == case_id)
        .order_by(CaseComment.created_at.asc())
        .all()
    )


def update_case(
    db: Session,
    *,
    case: Case,
    status: CaseStatus | None,
    assigned_to: str | None,
    priority: CasePriority | None,
    actor: str | None,
    now: datetime | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> Case:
    changed = False
    resolved_now = now or datetime.now(timezone.utc)
    change_entries: list[CaseEventChange] = []
    status_changed = False
    if status and status != case.status:
        previous = case.status
        case.status = status
        changed = True
        status_changed = True
        change_entries.append(
            CaseEventChange(field="status", before=previous.value, after=status.value)
        )
        db.add(
                CaseComment(
                    case_id=case.id,
                    author=actor,
                    type=CaseCommentType.SYSTEM,
                    body=f"Статус изменён {previous.value} → {status.value}",
                    created_at=resolved_now,
                )
            )
    if assigned_to is not None and assigned_to != case.assigned_to:
        previous_assigned = case.assigned_to
        case.assigned_to = assigned_to
        changed = True
        change_entries.append(
            CaseEventChange(field="assigned_to", before=previous_assigned, after=assigned_to)
        )
        if assigned_to:
            db.add(
                CaseComment(
                    case_id=case.id,
                    author=actor,
                    type=CaseCommentType.SYSTEM,
                    body=f"Назначено на {assigned_to}",
                    created_at=resolved_now,
                )
            )
    if priority and priority != case.priority:
        previous_priority = case.priority
        case.priority = priority
        changed = True
        change_entries.append(
            CaseEventChange(field="priority", before=previous_priority.value, after=priority.value)
        )
        db.add(
                CaseComment(
                    case_id=case.id,
                    author=actor,
                    body=f"Priority set to {priority.value}",
                    created_at=resolved_now,
                )
        )
    if changed:
        case.updated_at = resolved_now
        case.last_activity_at = resolved_now
        if status_changed:
            emit_case_event(
                db,
                case_id=case.id,
                event_type=CaseEventType.STATUS_CHANGED,
                actor=CaseEventActor(id=actor, email=None) if actor else None,
                request_id=request_id,
                trace_id=trace_id,
                changes=change_entries,
                at=resolved_now,
            )
    return case


def close_case(
    db: Session,
    *,
    case: Case,
    actor: str | None,
    resolution_note: str | None,
    score_snapshot: dict[str, Any] | None,
    mastery_snapshot: dict[str, Any] | None,
    now: datetime | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> Case:
    resolved_now = now or datetime.now(timezone.utc)
    previous = case.status
    case.status = CaseStatus.CLOSED
    case.updated_at = resolved_now
    case.last_activity_at = resolved_now
    db.add(
        CaseComment(
            case_id=case.id,
            author=actor,
            type=CaseCommentType.SYSTEM,
            body="Кейс закрыт",
        )
    )
    changes = [
        CaseEventChange(field="status", before=previous.value, after=case.status.value),
        CaseEventChange(field="closed_at", before=None, after=resolved_now.isoformat()),
    ]
    if resolution_note is not None:
        changes.append(CaseEventChange(field="resolution_note", before=None, after=resolution_note))
    event = emit_case_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.CASE_CLOSED,
        actor=CaseEventActor(id=actor, email=None) if actor else None,
        request_id=request_id,
        trace_id=trace_id,
        changes=changes,
        at=resolved_now,
    )
    record_decision_memory(
        db,
        case_id=case.id,
        decision_type="close",
        decision_ref_id=event.id,
        decision_at=resolved_now,
        decided_by_user_id=actor,
        context_snapshot={
            "case_id": str(case.id),
            "status": case.status.value,
            "resolution_note": resolution_note,
        },
        rationale=resolution_note,
        score_snapshot=score_snapshot,
        mastery_snapshot=mastery_snapshot,
        audit_event_id=event.id,
    )
    if case.queue == CaseQueue.SUPPORT:
        case_metrics.mark_support_ticket_closed()
    return case


def add_comment(
    db: Session,
    *,
    case: Case,
    author: str | None,
    body: str,
    comment_type: CaseCommentType = CaseCommentType.USER,
    now: datetime | None = None,
) -> CaseComment:
    resolved_now = now or datetime.now(timezone.utc)
    comment = CaseComment(
        case_id=case.id,
        author=author,
        type=comment_type,
        body=body,
        created_at=resolved_now,
    )
    db.add(comment)
    case.updated_at = resolved_now
    case.last_activity_at = resolved_now
    return comment


__all__ = [
    "add_comment",
    "close_case",
    "create_case",
    "get_case",
    "list_case_comments",
    "list_case_snapshots",
    "list_cases",
    "update_case",
]

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseComment, CaseKind, CasePriority, CaseSnapshot, CaseStatus


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
    tenant_id: int,
    kind: CaseKind,
    entity_id: str | None,
    kpi_key: str | None,
    window_days: int | None,
    title: str | None,
    priority: CasePriority,
    note: str | None,
    explain: dict[str, Any] | None,
    diff: dict[str, Any] | None,
    selected_actions: list[dict[str, Any]] | None,
    created_by: str | None,
) -> Case:
    now = datetime.now(timezone.utc)
    resolved_title = title or _build_case_title(
        kind=kind,
        entity_id=entity_id,
        kpi_key=kpi_key,
        explain=explain,
        diff=diff,
    )
    case = Case(
        tenant_id=tenant_id,
        kind=kind,
        entity_id=entity_id,
        kpi_key=kpi_key,
        window_days=window_days,
        title=resolved_title,
        status=CaseStatus.TRIAGE,
        priority=priority,
        created_by=created_by,
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
        note=note,
    )
    db.add(snapshot)
    return case


def list_cases(
    db: Session,
    *,
    tenant_id: int,
    created_by: str | None = None,
    status: CaseStatus | None = None,
    kind: CaseKind | None = None,
    priority: CasePriority | None = None,
    q: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[Case], int, str | None]:
    query = db.query(Case).filter(Case.tenant_id == tenant_id)
    if created_by:
        query = query.filter(Case.created_by == created_by)
    if status:
        query = query.filter(Case.status == status)
    if kind:
        query = query.filter(Case.kind == kind)
    if priority:
        query = query.filter(Case.priority == priority)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Case.title.ilike(pattern),
                Case.entity_id.ilike(pattern),
                Case.kpi_key.ilike(pattern),
            )
        )

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
) -> Case:
    changed = False
    now = datetime.now(timezone.utc)
    if status and status != case.status:
        case.status = status
        changed = True
        db.add(
            CaseComment(
                case_id=case.id,
                author=actor,
                body=f"Status changed to {status.value}",
            )
        )
    if assigned_to is not None and assigned_to != case.assigned_to:
        case.assigned_to = assigned_to
        changed = True
        if assigned_to:
            db.add(
                CaseComment(
                    case_id=case.id,
                    author=actor,
                    body=f"Assigned to {assigned_to}",
                )
            )
    if priority and priority != case.priority:
        case.priority = priority
        changed = True
        db.add(
            CaseComment(
                case_id=case.id,
                author=actor,
                body=f"Priority set to {priority.value}",
            )
        )
    if changed:
        case.updated_at = now
        case.last_activity_at = now
    return case


def add_comment(
    db: Session,
    *,
    case: Case,
    author: str | None,
    body: str,
) -> CaseComment:
    now = datetime.now(timezone.utc)
    comment = CaseComment(case_id=case.id, author=author, body=body)
    db.add(comment)
    case.updated_at = now
    case.last_activity_at = now
    return comment


__all__ = [
    "add_comment",
    "create_case",
    "get_case",
    "list_case_comments",
    "list_case_snapshots",
    "list_cases",
    "update_case",
]

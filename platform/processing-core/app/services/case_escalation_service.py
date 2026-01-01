from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.cases import (
    Case,
    CaseComment,
    CaseCommentType,
    CasePriority,
    CaseQueue,
    CaseSlaState,
    CaseStatus,
)
from app.services.cases_metrics import metrics as case_metrics
from neft_shared.logging_setup import get_logger


logger = get_logger(__name__)

DEFAULT_FIRST_RESPONSE_MINUTES = 60
DEFAULT_RESOLVE_MINUTES = 24 * 60
WARNING_WINDOW = timedelta(minutes=60)

FRAUD_REASON_KEYWORDS = {
    "velocity",
    "geo",
    "anomaly",
    "risk",
    "mismatch",
    "device",
    "ip",
    "station_outlier",
}
FINANCE_REASON_KEYWORDS = {
    "billing",
    "invoice",
    "export",
    "payout",
    "clearing",
    "settlement",
    "reconcile",
}
FRAUD_EVIDENCE_SOURCES = {"risk", "fuel_tx"}
FINANCE_EVIDENCE_SOURCES = {"billing", "bi", "exports"}


@dataclass(frozen=True)
class ClassificationResult:
    queue: CaseQueue
    first_response_minutes: int
    resolve_minutes: int
    matched_rules: list[str]
    priority_override: CasePriority | None = None
    assigned_to: str | None = None


def _normalize_values(items: Iterable[Any]) -> list[str]:
    return [str(item).strip().lower() for item in items if item is not None and str(item).strip()]


def _extract_reason_codes(explain_snapshot: dict[str, Any] | None, diff_snapshot: dict[str, Any] | None) -> list[str]:
    reason_codes: list[str] = []
    for snapshot in (explain_snapshot or {}, diff_snapshot or {}):
        if not isinstance(snapshot, dict):
            continue
        for key in ("reason_codes", "reasons", "reason_code"):
            value = snapshot.get(key)
            if isinstance(value, list):
                reason_codes.extend(value)
            elif isinstance(value, str):
                reason_codes.append(value)
        reasons_diff = snapshot.get("reasons_diff")
        if isinstance(reasons_diff, list):
            for item in reasons_diff:
                if not isinstance(item, dict):
                    continue
                code = item.get("reason_code") or item.get("code") or item.get("id")
                if code:
                    reason_codes.append(code)
    return _normalize_values(reason_codes)


def _extract_sources(snapshot: dict[str, Any] | None) -> list[str]:
    sources: list[str] = []
    if not snapshot or not isinstance(snapshot, dict):
        return sources
    for key in ("sources", "evidence_sources"):
        value = snapshot.get(key)
        if isinstance(value, list):
            sources.extend(value)
        elif isinstance(value, str):
            sources.append(value)
    evidence = snapshot.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                source = item.get("source")
                if source:
                    sources.append(source)
    return _normalize_values(sources)


def _has_anomaly_evidence(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot or not isinstance(snapshot, dict):
        return False
    evidence = snapshot.get("evidence")
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip().lower()
        if source not in FRAUD_EVIDENCE_SOURCES:
            continue
        if item.get("anomaly") or item.get("anomaly_flags") or item.get("flags") or item.get("risk_flags"):
            return True
    return False


def _format_minutes(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours}h"
    return f"{minutes}m"


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def classify_case(
    case: Case,
    explain_snapshot: dict[str, Any] | None,
    diff_snapshot: dict[str, Any] | None,
) -> ClassificationResult:
    reason_codes = _extract_reason_codes(explain_snapshot, diff_snapshot)
    sources = _extract_sources(explain_snapshot)
    matched_rules: list[str] = []

    for code in reason_codes:
        if any(keyword in code for keyword in FRAUD_REASON_KEYWORDS):
            matched_rules.append(f"reason_code:{code}")
    if _has_anomaly_evidence(explain_snapshot):
        matched_rules.append("evidence:risk_anomaly")
        return ClassificationResult(
            queue=CaseQueue.FRAUD_OPS,
            first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
            resolve_minutes=DEFAULT_RESOLVE_MINUTES,
            matched_rules=matched_rules,
        )
    if matched_rules:
        return ClassificationResult(
            queue=CaseQueue.FRAUD_OPS,
            first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
            resolve_minutes=DEFAULT_RESOLVE_MINUTES,
            matched_rules=matched_rules,
        )

    finance_matches = []
    for code in reason_codes:
        if any(keyword in code for keyword in FINANCE_REASON_KEYWORDS):
            finance_matches.append(f"reason_code:{code}")
    finance_sources = [source for source in sources if source in FINANCE_EVIDENCE_SOURCES]
    finance_matches.extend([f"evidence_source:{source}" for source in finance_sources])
    if finance_matches:
        return ClassificationResult(
            queue=CaseQueue.FINANCE_OPS,
            first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
            resolve_minutes=DEFAULT_RESOLVE_MINUTES,
            matched_rules=finance_matches,
        )

    return ClassificationResult(
        queue=CaseQueue.SUPPORT,
        first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
        resolve_minutes=DEFAULT_RESOLVE_MINUTES,
        matched_rules=["fallback:support"],
    )


def apply_classification(
    db: Session,
    *,
    case: Case,
    result: ClassificationResult,
    now: datetime | None = None,
) -> None:
    resolved_now = now or datetime.now(timezone.utc)
    case.queue = result.queue
    if result.priority_override:
        case.priority = result.priority_override
    if result.assigned_to:
        case.assigned_to = result.assigned_to
    if result.first_response_minutes:
        case.first_response_due_at = resolved_now + timedelta(minutes=result.first_response_minutes)
    if result.resolve_minutes:
        case.resolve_due_at = resolved_now + timedelta(minutes=result.resolve_minutes)

    routing_rules = ", ".join(result.matched_rules) if result.matched_rules else "default"
    db.add(
        CaseComment(
            case_id=case.id,
            author=None,
            type=CaseCommentType.SYSTEM,
            body=f"Маршрутизация: {result.queue.value} (rule: {routing_rules})",
        )
    )
    first_response_label = _format_minutes(result.first_response_minutes)
    resolve_label = _format_minutes(result.resolve_minutes)
    db.add(
        CaseComment(
            case_id=case.id,
            author=None,
            type=CaseCommentType.SYSTEM,
            body=f"SLA: first response {first_response_label}, resolve {resolve_label}",
        )
    )


def compute_sla_state(
    case: Case,
    *,
    now: datetime | None = None,
    warning_window: timedelta = WARNING_WINDOW,
) -> CaseSlaState:
    resolved_now = now or datetime.now(timezone.utc)
    resolved_now = _ensure_aware(resolved_now)
    first_response_due_at = _ensure_aware(case.first_response_due_at)
    resolve_due_at = _ensure_aware(case.resolve_due_at)
    if case.status in {CaseStatus.RESOLVED, CaseStatus.CLOSED}:
        return CaseSlaState.ON_TRACK

    breached = False
    if first_response_due_at and resolved_now > first_response_due_at:
        breached = True
    if resolve_due_at and resolved_now > resolve_due_at:
        breached = True
    if breached:
        return CaseSlaState.BREACHED

    warning_cutoff = resolved_now + warning_window
    if first_response_due_at and resolved_now <= first_response_due_at <= warning_cutoff:
        return CaseSlaState.WARNING
    if resolve_due_at and resolved_now <= resolve_due_at <= warning_cutoff:
        return CaseSlaState.WARNING
    return CaseSlaState.ON_TRACK


def _sla_breached_filter(now: datetime):
    return and_(
        Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CLOSED]),
        or_(
            and_(Case.first_response_due_at.isnot(None), Case.first_response_due_at < now),
            and_(Case.resolve_due_at.isnot(None), Case.resolve_due_at < now),
        ),
    )


def _sla_warning_filter(now: datetime, warning_window: timedelta):
    warning_cutoff = now + warning_window
    return and_(
        Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CLOSED]),
        or_(
            and_(
                Case.first_response_due_at.isnot(None),
                Case.first_response_due_at >= now,
                Case.first_response_due_at <= warning_cutoff,
            ),
            and_(
                Case.resolve_due_at.isnot(None),
                Case.resolve_due_at >= now,
                Case.resolve_due_at <= warning_cutoff,
            ),
        ),
    )


def apply_sla_filter(query, *, sla_state: CaseSlaState, now: datetime) -> Any:
    if sla_state == CaseSlaState.BREACHED:
        return query.filter(_sla_breached_filter(now))
    if sla_state == CaseSlaState.WARNING:
        return query.filter(_sla_warning_filter(now, WARNING_WINDOW)).filter(~_sla_breached_filter(now))
    if sla_state == CaseSlaState.ON_TRACK:
        return query.filter(~_sla_breached_filter(now)).filter(~_sla_warning_filter(now, WARNING_WINDOW))
    return query


def evaluate_escalations(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    resolved_now = now or datetime.now(timezone.utc)
    escalated_first = 0
    escalated_resolve = 0

    first_response_cases = (
        db.query(Case)
        .filter(Case.escalation_level == 0)
        .filter(Case.first_response_due_at.isnot(None))
        .filter(Case.first_response_due_at < resolved_now)
        .filter(Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CLOSED]))
        .filter(Case.last_activity_at <= Case.first_response_due_at)
        .all()
    )
    for case in first_response_cases:
        case.escalation_level = 1
        case.updated_at = resolved_now
        db.add(
            CaseComment(
                case_id=case.id,
                author=None,
                type=CaseCommentType.SYSTEM,
                body="Эскалация уровня 1: нарушен SLA первого ответа",
            )
        )
        escalated_first += 1
        case_metrics.mark_escalation(level=1)
        case_metrics.mark_sla_breach("first_response")

    resolve_cases = (
        db.query(Case)
        .filter(Case.escalation_level < 2)
        .filter(Case.resolve_due_at.isnot(None))
        .filter(Case.resolve_due_at < resolved_now)
        .filter(Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CLOSED]))
        .all()
    )
    for case in resolve_cases:
        if case.escalation_level >= 2:
            continue
        case.escalation_level = 2
        case.updated_at = resolved_now
        db.add(
            CaseComment(
                case_id=case.id,
                author=None,
                type=CaseCommentType.SYSTEM,
                body="Эскалация уровня 2: нарушен SLA решения",
            )
        )
        escalated_resolve += 1
        case_metrics.mark_escalation(level=2)
        case_metrics.mark_sla_breach("resolve")

    if escalated_first or escalated_resolve:
        logger.info(
            "cases_escalations_applied",
            extra={"first_response": escalated_first, "resolve": escalated_resolve},
        )

    return {"first_response": escalated_first, "resolve": escalated_resolve}


__all__ = [
    "ClassificationResult",
    "apply_classification",
    "apply_sla_filter",
    "classify_case",
    "compute_sla_state",
    "evaluate_escalations",
]

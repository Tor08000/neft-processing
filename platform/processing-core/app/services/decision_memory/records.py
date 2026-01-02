from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryRecord
from app.services.case_event_redaction import redact_deep


def _redact_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    return redact_deep(snapshot, "", include_hash=True)


def _normalize_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return None
    return str(value)


def _extract_score_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot or not isinstance(snapshot, dict):
        return None
    if isinstance(snapshot.get("score_snapshot"), dict):
        return snapshot.get("score_snapshot")
    score_fields = {}
    for key in ("score", "penalty", "confidence"):
        if key in snapshot:
            score_fields[key] = snapshot[key]
    return score_fields or None


def record_decision_memory(
    db: Session,
    *,
    case_id: str | None,
    decision_type: str,
    decision_ref_id: str,
    decision_at: datetime,
    decided_by_user_id: str | None,
    context_snapshot: dict[str, Any] | None,
    rationale: str | None,
    score_snapshot: dict[str, Any] | None,
    mastery_snapshot: dict[str, Any] | None,
    audit_event_id: str,
) -> DecisionMemoryRecord:
    record = DecisionMemoryRecord(
        case_id=case_id,
        decision_type=decision_type,
        decision_ref_id=decision_ref_id,
        decision_at=decision_at,
        decided_by_user_id=_normalize_uuid(decided_by_user_id),
        context_snapshot=_redact_snapshot(context_snapshot),
        rationale=rationale,
        score_snapshot=score_snapshot,
        mastery_snapshot=mastery_snapshot,
        audit_event_id=audit_event_id,
    )
    db.add(record)
    return record


def list_decision_memory_for_case(
    db: Session,
    *,
    case_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[DecisionMemoryRecord]:
    return (
        db.query(DecisionMemoryRecord)
        .filter(DecisionMemoryRecord.case_id == case_id)
        .order_by(DecisionMemoryRecord.decision_at.desc(), DecisionMemoryRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


__all__ = [
    "_extract_score_snapshot",
    "list_decision_memory_for_case",
    "record_decision_memory",
]

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.dispute import Dispute, DisputeStatus
from app.models.risk_types import RiskSubjectType
from app.models.risk_v5_label import RiskV5Label, RiskV5LabelRecord, RiskV5LabelSource


@dataclass(frozen=True)
class LabelCandidate:
    label: RiskV5Label
    source: RiskV5LabelSource
    confidence: int


OVERRIDE_EVENT_MAP = {
    "RISK_DECISION_OVERRIDE_BLOCK": RiskV5Label.FRAUD,
    "RISK_DECISION_OVERRIDE_ALLOW": RiskV5Label.NOT_FRAUD,
}


def resolve_label(
    db: Session,
    *,
    decision_id: str,
    subject_type: RiskSubjectType,
    subject_id: str,
) -> LabelCandidate | None:
    override_label = from_overrides(db, decision_id=decision_id)
    if override_label is not None:
        return override_label

    outcome_label = from_outcomes(db, subject_type=subject_type, subject_id=subject_id)
    if outcome_label is not None:
        return outcome_label

    return None


def persist_label(
    db: Session,
    *,
    decision_id: str,
    subject_type: RiskSubjectType,
    subject_id: str,
    label: LabelCandidate,
) -> RiskV5LabelRecord:
    record = RiskV5LabelRecord(
        decision_id=decision_id,
        subject_type=subject_type,
        subject_id=subject_id,
        label=label.label,
        label_source=label.source,
        confidence=label.confidence,
    )
    db.add(record)
    db.flush()
    return record


def from_overrides(db: Session, *, decision_id: str) -> LabelCandidate | None:
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type.in_(["decision", "risk_decision"]),
            AuditLog.entity_id == decision_id,
        )
        .order_by(AuditLog.ts.desc())
        .first()
    )
    if audit is None:
        return None
    label = OVERRIDE_EVENT_MAP.get(audit.event_type)
    if label is None:
        return None
    return LabelCandidate(label=label, source=RiskV5LabelSource.OVERRIDE, confidence=95)


def from_outcomes(
    db: Session,
    *,
    subject_type: RiskSubjectType,
    subject_id: str,
) -> LabelCandidate | None:
    if subject_type != RiskSubjectType.PAYMENT:
        return None
    dispute = (
        db.query(Dispute)
        .filter(Dispute.operation_id == subject_id)
        .order_by(Dispute.created_at.desc())
        .first()
    )
    if dispute is None:
        return None
    if dispute.status == DisputeStatus.ACCEPTED:
        return LabelCandidate(label=RiskV5Label.FRAUD, source=RiskV5LabelSource.DISPUTE, confidence=80)
    if dispute.status == DisputeStatus.REJECTED:
        return LabelCandidate(label=RiskV5Label.NOT_FRAUD, source=RiskV5LabelSource.DISPUTE, confidence=70)
    return None


__all__ = [
    "LabelCandidate",
    "from_outcomes",
    "from_overrides",
    "persist_label",
    "resolve_label",
]

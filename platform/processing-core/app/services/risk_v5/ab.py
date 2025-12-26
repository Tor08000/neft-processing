from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.risk_types import RiskSubjectType
from app.models.risk_v5_ab_assignment import RiskV5ABAssignment
from app.services.risk_v5.config import get_risk_v5_config


@dataclass(frozen=True)
class AssignmentDecision:
    bucket: str
    source: str


def determine_bucket(*, client_id: str | None, subject_type: RiskSubjectType, salt: str, weight_b: int) -> str:
    identity = f"{client_id or 'anonymous'}:{subject_type.value}:{salt}".encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()
    bucket_value = int(digest[:8], 16) % 100
    threshold_b = max(0, min(weight_b, 100))
    return "B" if bucket_value < threshold_b else "A"


def resolve_assignment(
    db: Session | None,
    *,
    tenant_id: int | None,
    client_id: str | None,
    subject_type: RiskSubjectType,
) -> AssignmentDecision:
    config = get_risk_v5_config()
    if db is not None:
        assignment = _lookup_assignment(db, tenant_id=tenant_id, client_id=client_id, subject_type=subject_type)
        if assignment is not None:
            return AssignmentDecision(bucket=assignment.bucket, source="db")
    bucket = determine_bucket(
        client_id=client_id,
        subject_type=subject_type,
        salt=config.ab_salt,
        weight_b=config.ab_weight_b,
    )
    return AssignmentDecision(bucket=bucket, source="hash")


def create_assignment(
    db: Session,
    *,
    tenant_id: int | None,
    client_id: str | None,
    subject_type: RiskSubjectType,
    bucket: str,
    weight: int,
    active: bool,
) -> RiskV5ABAssignment:
    assignment = RiskV5ABAssignment(
        tenant_id=tenant_id,
        client_id=client_id,
        subject_type=subject_type,
        bucket=bucket,
        weight=weight,
        active=active,
    )
    db.add(assignment)
    db.flush()
    return assignment


def _lookup_assignment(
    db: Session,
    *,
    tenant_id: int | None,
    client_id: str | None,
    subject_type: RiskSubjectType,
) -> RiskV5ABAssignment | None:
    query = db.query(RiskV5ABAssignment).filter(
        RiskV5ABAssignment.active.is_(True),
        RiskV5ABAssignment.subject_type == subject_type,
    )
    if client_id:
        query = query.filter(RiskV5ABAssignment.client_id == client_id)
    elif tenant_id:
        query = query.filter(RiskV5ABAssignment.tenant_id == tenant_id, RiskV5ABAssignment.client_id.is_(None))
    else:
        query = query.filter(RiskV5ABAssignment.client_id.is_(None), RiskV5ABAssignment.tenant_id.is_(None))
    return query.order_by(RiskV5ABAssignment.created_at.desc()).first()


__all__ = ["AssignmentDecision", "create_assignment", "determine_bucket", "resolve_assignment"]

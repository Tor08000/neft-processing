from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdScope


@dataclass(frozen=True)
class PolicySelection:
    policy: RiskPolicy | None
    threshold_set: RiskThresholdSet
    threshold: RiskThreshold | None


def resolve_policy(
    db: Session,
    *,
    subject_type: RiskSubjectType,
    tenant_id: int | None,
    client_id: str | None,
    provider: str | None,
    currency: str | None,
    country: str | None,
) -> RiskPolicy | None:
    query = db.query(RiskPolicy).filter(
        RiskPolicy.active.is_(True),
        RiskPolicy.subject_type == subject_type,
    )
    query = _apply_match(query, RiskPolicy.tenant_id, tenant_id)
    query = _apply_match(query, RiskPolicy.client_id, client_id)
    query = _apply_match(query, RiskPolicy.provider, provider)
    query = _apply_match(query, RiskPolicy.currency, currency)
    query = _apply_match(query, RiskPolicy.country, country)

    policies = query.all()
    if not policies:
        return None

    # Resolution order is fixed: lower priority wins, then higher specificity.
    return sorted(policies, key=lambda item: (item.priority, -_specificity(item)))[0]


def resolve_threshold_set(
    db: Session,
    *,
    subject_type: RiskSubjectType,
    threshold_set_id: str | None,
) -> RiskThresholdSet | None:
    query = db.query(RiskThresholdSet).filter(
        RiskThresholdSet.active.is_(True),
        RiskThresholdSet.subject_type == subject_type,
    )
    if threshold_set_id is not None:
        query = query.filter(RiskThresholdSet.id == threshold_set_id)
    else:
        query = query.filter(RiskThresholdSet.scope == RiskThresholdScope.GLOBAL)
    return query.order_by(RiskThresholdSet.version.desc()).first()


def resolve_threshold(
    db: Session,
    *,
    threshold_set_id: str,
    subject_type: RiskSubjectType,
    score: int,
    now: datetime | None = None,
) -> RiskThreshold | None:
    """Resolve a single threshold row for the given score within a threshold set."""
    now = now or datetime.now(timezone.utc)
    return (
        db.query(RiskThreshold)
        .filter(
            RiskThreshold.active.is_(True),
            RiskThreshold.threshold_set_id == threshold_set_id,
            RiskThreshold.subject_type == subject_type,
            RiskThreshold.min_score <= score,
            RiskThreshold.max_score >= score,
            RiskThreshold.valid_from <= now,
            or_(RiskThreshold.valid_to.is_(None), RiskThreshold.valid_to >= now),
        )
        .order_by(RiskThreshold.priority.asc())
        .first()
    )


def resolve_policy_threshold(
    db: Session,
    *,
    subject_type: RiskSubjectType,
    score: int,
    tenant_id: int | None,
    client_id: str | None,
    provider: str | None,
    currency: str | None,
    country: str | None,
    now: datetime | None = None,
) -> PolicySelection | None:
    """Resolve the policy, threshold set, and threshold for a given decision."""
    policy = resolve_policy(
        db,
        subject_type=subject_type,
        tenant_id=tenant_id,
        client_id=client_id,
        provider=provider,
        currency=currency,
        country=country,
    )
    threshold_set = resolve_threshold_set(
        db,
        subject_type=subject_type,
        threshold_set_id=policy.threshold_set_id if policy else None,
    )
    if threshold_set is None:
        threshold_set = resolve_threshold_set(db, subject_type=subject_type, threshold_set_id=None)
    if threshold_set is None:
        return None
    threshold = resolve_threshold(
        db,
        threshold_set_id=threshold_set.id,
        subject_type=subject_type,
        score=score,
        now=now,
    )
    return PolicySelection(policy=policy, threshold_set=threshold_set, threshold=threshold)


def _apply_match(query, column, value):
    if value is None:
        return query.filter(column.is_(None))
    return query.filter(or_(column.is_(None), column == value))


def _specificity(policy: RiskPolicy) -> int:
    score = 0
    if policy.tenant_id is not None:
        score += 1
    if policy.client_id:
        score += 1
    if policy.provider:
        score += 1
    if policy.currency:
        score += 1
    if policy.country:
        score += 1
    return score


__all__ = [
    "PolicySelection",
    "resolve_policy",
    "resolve_policy_threshold",
    "resolve_threshold",
    "resolve_threshold_set",
]

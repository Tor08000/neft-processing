from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.decision_memory import (
    DecisionActionStatsDaily,
    DecisionMemoryEffectLabel,
    DecisionMemoryEntityType,
    DecisionOutcome,
)


def get_outcome_by_applied_action_id(db: Session, *, applied_action_id: str) -> DecisionOutcome | None:
    return (
        db.query(DecisionOutcome)
        .filter(DecisionOutcome.applied_action_id == applied_action_id)
        .one_or_none()
    )


def get_outcome_by_idempotency(
    db: Session,
    *,
    tenant_id: int,
    entity_type: DecisionMemoryEntityType,
    entity_id: str,
    action_code: str,
    applied_day: date,
) -> DecisionOutcome | None:
    return (
        db.query(DecisionOutcome)
        .filter(DecisionOutcome.tenant_id == tenant_id)
        .filter(DecisionOutcome.entity_type == entity_type)
        .filter(DecisionOutcome.entity_id == entity_id)
        .filter(DecisionOutcome.action_code == action_code)
        .filter(func.date(DecisionOutcome.applied_at) == applied_day)
        .one_or_none()
    )


def add_outcome(db: Session, *, outcome: DecisionOutcome) -> DecisionOutcome:
    applied_action_id = outcome.applied_action_id
    if applied_action_id:
        pending = _find_pending_outcome(db, applied_action_id=str(applied_action_id))
        if pending:
            return pending
        existing = get_outcome_by_applied_action_id(db, applied_action_id=str(applied_action_id))
        if existing:
            return existing
    applied_day = outcome.applied_at.date()
    existing = get_outcome_by_idempotency(
        db,
        tenant_id=outcome.tenant_id,
        entity_type=outcome.entity_type,
        entity_id=outcome.entity_id,
        action_code=outcome.action_code,
        applied_day=applied_day,
    )
    if existing:
        return existing
    db.add(outcome)
    return outcome


def list_outcomes_for_entity(
    db: Session,
    *,
    entity_type: DecisionMemoryEntityType,
    entity_id: str,
    limit: int = 20,
) -> list[DecisionOutcome]:
    return (
        db.query(DecisionOutcome)
        .filter(DecisionOutcome.entity_type == entity_type)
        .filter(DecisionOutcome.entity_id == entity_id)
        .order_by(DecisionOutcome.applied_at.desc())
        .limit(limit)
        .all()
    )


def list_recent_outcomes(
    db: Session,
    *,
    entity_type: DecisionMemoryEntityType,
    entity_id: str,
    action_code: str | None = None,
    cutoff: datetime | None = None,
) -> list[DecisionOutcome]:
    query = (
        db.query(DecisionOutcome)
        .filter(DecisionOutcome.entity_type == entity_type)
        .filter(DecisionOutcome.entity_id == entity_id)
    )
    if action_code:
        query = query.filter(DecisionOutcome.action_code == action_code)
    if cutoff:
        query = query.filter(DecisionOutcome.applied_at >= cutoff)
    return query.order_by(DecisionOutcome.applied_at.desc()).all()


def list_outcomes_for_action(
    db: Session,
    *,
    tenant_id: int | None = None,
    client_id: str | None = None,
    action_code: str,
    entity_type: DecisionMemoryEntityType | None = None,
    start_day: date | None = None,
) -> list[DecisionOutcome]:
    query = db.query(DecisionOutcome).filter(DecisionOutcome.action_code == action_code)
    if tenant_id is not None:
        query = query.filter(DecisionOutcome.tenant_id == tenant_id)
    if client_id is not None:
        query = query.filter(DecisionOutcome.client_id == client_id)
    if entity_type is not None:
        query = query.filter(DecisionOutcome.entity_type == entity_type)
    if start_day is not None:
        query = query.filter(DecisionOutcome.applied_at >= start_day)
    return query.order_by(DecisionOutcome.applied_at.desc()).all()


def upsert_action_stats_daily(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    action_code: str,
    entity_type: DecisionMemoryEntityType,
    day: date,
    effect_label: DecisionMemoryEffectLabel,
) -> DecisionActionStatsDaily:
    record = _find_pending_daily_stats(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        action_code=action_code,
        entity_type=entity_type,
        day=day,
    )
    if not record:
        record = (
            db.query(DecisionActionStatsDaily)
            .filter(DecisionActionStatsDaily.tenant_id == tenant_id)
            .filter(DecisionActionStatsDaily.action_code == action_code)
            .filter(DecisionActionStatsDaily.entity_type == entity_type)
            .filter(DecisionActionStatsDaily.day == day)
            .filter(
                DecisionActionStatsDaily.client_id.is_(client_id)
                if client_id is None
                else DecisionActionStatsDaily.client_id == client_id
            )
            .one_or_none()
        )
    if not record:
        record = DecisionActionStatsDaily(
            tenant_id=tenant_id,
            client_id=client_id,
            action_code=action_code,
            entity_type=entity_type,
            day=day,
            applied_count=0,
            improved_count=0,
            no_change_count=0,
            worse_count=0,
            weighted_success=0.0,
        )
        db.add(record)
    record.applied_count = (record.applied_count or 0) + 1
    if effect_label == DecisionMemoryEffectLabel.IMPROVED:
        record.improved_count = (record.improved_count or 0) + 1
        record.weighted_success = (record.weighted_success or 0.0) + 1.0
    elif effect_label == DecisionMemoryEffectLabel.NO_CHANGE:
        record.no_change_count = (record.no_change_count or 0) + 1
    elif effect_label == DecisionMemoryEffectLabel.WORSE:
        record.worse_count = (record.worse_count or 0) + 1
    return record


def _find_pending_outcome(db: Session, *, applied_action_id: str) -> DecisionOutcome | None:
    for item in db.new:
        if isinstance(item, DecisionOutcome) and str(item.applied_action_id) == applied_action_id:
            return item
    return None


def _find_pending_daily_stats(
    db: Session,
    *,
    tenant_id: int,
    client_id: str | None,
    action_code: str,
    entity_type: DecisionMemoryEntityType,
    day: date,
) -> DecisionActionStatsDaily | None:
    for item in db.new:
        if not isinstance(item, DecisionActionStatsDaily):
            continue
        if item.tenant_id != tenant_id:
            continue
        if item.client_id != client_id:
            continue
        if item.action_code != action_code:
            continue
        if item.entity_type != entity_type:
            continue
        if item.day != day:
            continue
        return item
    return None


def list_stats_daily(
    db: Session,
    *,
    tenant_id: int,
    action_code: str,
    entity_type: DecisionMemoryEntityType | None = None,
    client_id: str | None = None,
    start_day: date | None = None,
) -> list[DecisionActionStatsDaily]:
    query = (
        db.query(DecisionActionStatsDaily)
        .filter(DecisionActionStatsDaily.tenant_id == tenant_id)
        .filter(DecisionActionStatsDaily.action_code == action_code)
    )
    if entity_type is not None:
        query = query.filter(DecisionActionStatsDaily.entity_type == entity_type)
    if client_id is not None:
        query = query.filter(DecisionActionStatsDaily.client_id == client_id)
    if start_day is not None:
        query = query.filter(DecisionActionStatsDaily.day >= start_day)
    return query.order_by(DecisionActionStatsDaily.day.asc()).all()


__all__ = [
    "add_outcome",
    "get_outcome_by_applied_action_id",
    "get_outcome_by_idempotency",
    "list_outcomes_for_action",
    "list_outcomes_for_entity",
    "list_recent_outcomes",
    "list_stats_daily",
    "upsert_action_stats_daily",
]

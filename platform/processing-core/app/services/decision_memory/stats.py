from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionActionStatsDaily, DecisionMemoryEntityType
from app.services.decision_memory import defaults, repository


@dataclass(frozen=True)
class DecisionActionStats:
    action_code: str
    entity_type: DecisionMemoryEntityType
    window_days: int
    applied_count: int
    improved_count: int
    no_change_count: int
    worse_count: int
    success_rate: float
    weighted_success_rate: float
    weighted_success: float
    weighted_applied: float


def compute_action_stats(
    db: Session,
    *,
    tenant_id: int,
    action_code: str,
    entity_type: DecisionMemoryEntityType,
    window_days: int = defaults.MEMORY_WINDOW_DAYS,
    client_id: str | None = None,
    now: datetime | None = None,
) -> DecisionActionStats:
    now = now or datetime.now(timezone.utc)
    start_day = now.date() - timedelta(days=max(window_days - 1, 0))
    daily = repository.list_stats_daily(
        db,
        tenant_id=tenant_id,
        action_code=action_code,
        entity_type=entity_type,
        client_id=client_id,
        start_day=start_day,
    )
    return _aggregate_stats(
        daily,
        action_code=action_code,
        entity_type=entity_type,
        window_days=window_days,
        now=now,
    )


def list_action_stats(
    db: Session,
    *,
    tenant_id: int,
    action_code: str,
    window_days: int = defaults.MEMORY_WINDOW_DAYS,
    client_id: str | None = None,
    now: datetime | None = None,
) -> list[DecisionActionStats]:
    now = now or datetime.now(timezone.utc)
    start_day = now.date() - timedelta(days=max(window_days - 1, 0))
    daily = repository.list_stats_daily(
        db,
        tenant_id=tenant_id,
        action_code=action_code,
        client_id=client_id,
        start_day=start_day,
    )
    grouped: dict[DecisionMemoryEntityType, list[DecisionActionStatsDaily]] = {}
    for record in daily:
        grouped.setdefault(record.entity_type, []).append(record)
    return [
        _aggregate_stats(
            grouped[entity_type],
            action_code=action_code,
            entity_type=entity_type,
            window_days=window_days,
            now=now,
        )
        for entity_type in grouped
    ]


def build_action_stats_map(
    db: Session,
    *,
    tenant_id: int,
    action_codes: list[str],
    entity_type: DecisionMemoryEntityType,
    window_days: int = defaults.MEMORY_WINDOW_DAYS,
    client_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, DecisionActionStats]:
    now = now or datetime.now(timezone.utc)
    start_day = now.date() - timedelta(days=max(window_days - 1, 0))
    stats_map: dict[str, list[DecisionActionStatsDaily]] = {code: [] for code in action_codes}
    for code in action_codes:
        stats_map[code] = repository.list_stats_daily(
            db,
            tenant_id=tenant_id,
            action_code=code,
            entity_type=entity_type,
            client_id=client_id,
            start_day=start_day,
        )
    return {
        code: _aggregate_stats(
            stats_map[code],
            action_code=code,
            entity_type=entity_type,
            window_days=window_days,
            now=now,
        )
        for code in action_codes
    }


def _aggregate_stats(
    records: list[DecisionActionStatsDaily],
    *,
    action_code: str,
    entity_type: DecisionMemoryEntityType,
    window_days: int,
    now: datetime,
) -> DecisionActionStats:
    applied_count = sum(record.applied_count for record in records)
    improved_count = sum(record.improved_count for record in records)
    no_change_count = sum(record.no_change_count for record in records)
    worse_count = sum(record.worse_count for record in records)
    weighted_success = 0.0
    weighted_applied = 0.0
    for record in records:
        age_days = (now.date() - record.day).days
        weight = 0.5 ** (age_days / defaults.HALF_LIFE_DAYS) if defaults.HALF_LIFE_DAYS > 0 else 1.0
        weighted_success += record.improved_count * weight
        weighted_applied += record.applied_count * weight
    success_rate = improved_count / applied_count if applied_count else 0.0
    weighted_success_rate = weighted_success / weighted_applied if weighted_applied else 0.0
    return DecisionActionStats(
        action_code=action_code,
        entity_type=entity_type,
        window_days=window_days,
        applied_count=applied_count,
        improved_count=improved_count,
        no_change_count=no_change_count,
        worse_count=worse_count,
        success_rate=success_rate,
        weighted_success_rate=weighted_success_rate,
        weighted_success=weighted_success,
        weighted_applied=weighted_applied,
    )


__all__ = [
    "DecisionActionStats",
    "build_action_stats_map",
    "compute_action_stats",
    "list_action_stats",
]

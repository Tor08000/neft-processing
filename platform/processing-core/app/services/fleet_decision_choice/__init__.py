from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.decision_memory import DecisionMemoryEntityType
from app.models.fleet_decision_choice import FleetActionEffectStats
from app.services.decision_memory import cooldown as memory_cooldown
from app.services.decision_memory import stats as memory_stats
from app.services.fleet_decision_choice import candidates, defaults, explain, scorer
from app.services.fleet_decision_choice.evaluator import ActionEffectStats


def build_decision_choice(
    db: Session,
    *,
    insight_type: str,
    tenant_id: int | None = None,
    client_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    candidate_actions: list[str] | None = None,
    window_days: int | None = None,
    peer_percentiles: dict[str, float] | None = None,
    now: datetime | None = None,
) -> dict | None:
    window_days = window_days or defaults.DEFAULT_WINDOW_DAYS
    action_codes = candidates.list_candidate_actions(candidate_actions)
    stats = _load_action_effect_stats(
        db,
        action_codes=action_codes,
        insight_type=insight_type,
        window_days=window_days,
    )
    if not stats:
        return None
    cooldowns = None
    memory_map = None
    resolved_entity_type = _resolve_entity_type(entity_type)
    if resolved_entity_type and entity_id and tenant_id is not None:
        cooldowns = {
            action_code: memory_cooldown.evaluate_cooldown(
                db,
                entity_type=resolved_entity_type,
                entity_id=entity_id,
                action_code=action_code,
                now=now,
            )
            for action_code in action_codes
        }
        memory_map = memory_stats.build_action_stats_map(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            action_codes=action_codes,
            entity_type=resolved_entity_type,
            window_days=window_days,
            now=now,
        )
    return build_decision_choice_from_stats(
        stats,
        window_days=window_days,
        peer_percentiles=peer_percentiles,
        now=now,
        cooldowns=cooldowns,
        memory_stats=memory_map,
    )


def build_decision_choice_from_stats(
    stats: list[ActionEffectStats],
    *,
    window_days: int,
    peer_percentiles: dict[str, float] | None = None,
    now: datetime | None = None,
    cooldowns: dict[str, memory_cooldown.CooldownStatus] | None = None,
    memory_stats: dict[str, memory_stats.DecisionActionStats] | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    scored = scorer.score_actions(
        stats,
        peer_percentiles=peer_percentiles,
        now=now,
        cooldowns=cooldowns,
        memory_stats=memory_stats,
    )
    return explain.build_decision_choice_output(scored, window_days=window_days)


def _load_action_effect_stats(
    db: Session,
    *,
    action_codes: list[str],
    insight_type: str,
    window_days: int,
) -> list[ActionEffectStats]:
    if not action_codes:
        return []
    rows = (
        db.query(FleetActionEffectStats)
        .filter(FleetActionEffectStats.action_code.in_(action_codes))
        .filter(FleetActionEffectStats.insight_type == insight_type)
        .filter(FleetActionEffectStats.window_days == window_days)
        .all()
    )
    stats_map = {row.action_code: row for row in rows}
    result: list[ActionEffectStats] = []
    for code in action_codes:
        row = stats_map.get(code)
        if row:
            result.append(_row_to_stats(row))
        else:
            result.append(
                ActionEffectStats(
                    action_code=code,
                    insight_type=insight_type,
                    window_days=window_days,
                    applied_count=0,
                    improved_count=0,
                    no_change_count=0,
                    worsened_count=0,
                    avg_effect_delta=None,
                    last_computed_at=None,
                )
            )
    return result


def _row_to_stats(row: FleetActionEffectStats) -> ActionEffectStats:
    return ActionEffectStats(
        action_code=row.action_code,
        insight_type=row.insight_type,
        window_days=row.window_days,
        applied_count=row.applied_count,
        improved_count=row.improved_count,
        no_change_count=row.no_change_count,
        worsened_count=row.worsened_count,
        avg_effect_delta=float(row.avg_effect_delta) if row.avg_effect_delta is not None else None,
        last_computed_at=row.last_computed_at,
    )


def _resolve_entity_type(entity_type: str | None) -> DecisionMemoryEntityType | None:
    if not entity_type:
        return None
    try:
        return DecisionMemoryEntityType(entity_type)
    except ValueError:
        return None


__all__ = ["build_decision_choice", "build_decision_choice_from_stats"]

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.fleet_intelligence_actions import (
    FIActionEffect,
    FIActionEffectLabel,
    FIAppliedAction,
    FIInsightEntityType,
)
from app.services.decision_memory import store as decision_memory_store
from app.services.fleet_intelligence.control import defaults, repository


def build_before_state(db: Session, *, insight, as_of: datetime) -> dict[str, Any]:
    state: dict[str, Any] = {}
    day = as_of.date()
    start_day = day - timedelta(days=6)
    if insight.entity_type == FIInsightEntityType.DRIVER:
        score_7 = repository.get_latest_driver_score(
            db,
            tenant_id=insight.tenant_id,
            client_id=insight.client_id,
            driver_id=str(insight.entity_id),
            window_days=7,
            as_of=as_of,
        )
        score_30 = repository.get_latest_driver_score(
            db,
            tenant_id=insight.tenant_id,
            client_id=insight.client_id,
            driver_id=str(insight.entity_id),
            window_days=30,
            as_of=as_of,
        )
        state["driver_score_7d"] = score_7.score if score_7 else None
        state["driver_score_30d"] = score_30.score if score_30 else None
        state["fuel_anomalies_7d"] = repository.summarize_driver_anomalies(
            db,
            tenant_id=insight.tenant_id,
            driver_id=str(insight.entity_id),
            start_day=start_day,
            end_day=day,
        )
    if insight.entity_type == FIInsightEntityType.STATION:
        score_30 = repository.get_latest_station_score(
            db,
            tenant_id=insight.tenant_id,
            station_id=str(insight.entity_id),
            window_days=30,
            as_of=as_of,
        )
        state["station_trust_30d"] = score_30.trust_score if score_30 else None
    if insight.entity_type == FIInsightEntityType.VEHICLE:
        score_7 = repository.get_latest_vehicle_score(
            db,
            tenant_id=insight.tenant_id,
            client_id=insight.client_id,
            vehicle_id=str(insight.entity_id),
            window_days=7,
            as_of=as_of,
        )
        state["vehicle_efficiency_score_7d"] = score_7.efficiency_score if score_7 else None
        state["vehicle_efficiency_delta_pct_7d"] = score_7.delta_pct if score_7 else None
        state["logistics_deviations_7d"] = repository.summarize_vehicle_anomalies(
            db,
            tenant_id=insight.tenant_id,
            vehicle_id=str(insight.entity_id),
            start_day=start_day,
            end_day=day,
        )
    return state


def measure_action_effects(
    db: Session,
    *,
    as_of: datetime,
    window_days: int = 7,
) -> list[FIActionEffect]:
    cutoff = as_of - timedelta(days=window_days)
    actions = repository.list_actions_in_monitoring(db, cutoff=cutoff)
    effects: list[FIActionEffect] = []
    for action in actions:
        insight = repository.get_insight(db, insight_id=str(action.insight_id))
        if not insight:
            continue
        effect = _measure_single(db, action=action, insight=insight, as_of=as_of, window_days=window_days)
        if effect:
            effects.append(effect)
    return effects


def _measure_single(
    db: Session,
    *,
    action: FIAppliedAction,
    insight,
    as_of: datetime,
    window_days: int,
) -> FIActionEffect | None:
    baseline = action.before_state or {}
    current = build_before_state(db, insight=insight, as_of=as_of)
    delta = _calculate_delta(baseline, current)
    label = _label_effect(insight.entity_type, baseline, current)
    summary = _summary_for_label(label)
    effect = FIActionEffect(
        applied_action_id=action.id,
        measured_at=as_of,
        window_days=window_days,
        baseline=baseline,
        current=current,
        delta=delta,
        effect_label=label,
        summary=summary,
    )
    repository.add_action_effect(db, effect)
    decision_memory_store.record_outcome_from_effect(db, action=action, insight=insight, effect=effect)
    return effect


def _calculate_delta(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in baseline:
        before = baseline.get(key)
        after = current.get(key)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta[key] = after - before
    return delta


def _label_effect(entity_type: FIInsightEntityType, baseline: dict[str, Any], current: dict[str, Any]) -> FIActionEffectLabel:
    thresholds = defaults.EFFECT_THRESHOLDS
    if entity_type == FIInsightEntityType.DRIVER:
        before = baseline.get("driver_score_7d")
        after = current.get("driver_score_7d")
        return _label_numeric(before, after, thresholds.driver_score_improve_delta, thresholds.driver_score_worse_delta)
    if entity_type == FIInsightEntityType.STATION:
        before = baseline.get("station_trust_30d")
        after = current.get("station_trust_30d")
        return _label_numeric_increase_good(
            before,
            after,
            thresholds.station_trust_improve_delta,
            thresholds.station_trust_worse_delta,
        )
    if entity_type == FIInsightEntityType.VEHICLE:
        before = baseline.get("vehicle_efficiency_score_7d")
        after = current.get("vehicle_efficiency_score_7d")
        return _label_numeric(before, after, thresholds.vehicle_efficiency_improve_delta, thresholds.vehicle_efficiency_worse_delta)
    return FIActionEffectLabel.NO_CHANGE


def _label_numeric(
    before: int | float | None,
    after: int | float | None,
    improve_delta: int | float,
    worse_delta: int | float,
) -> FIActionEffectLabel:
    if before is None or after is None:
        return FIActionEffectLabel.NO_CHANGE
    change = after - before
    if change <= -abs(improve_delta):
        return FIActionEffectLabel.IMPROVED
    if change >= abs(worse_delta):
        return FIActionEffectLabel.WORSE
    return FIActionEffectLabel.NO_CHANGE


def _label_numeric_increase_good(
    before: int | float | None,
    after: int | float | None,
    improve_delta: int | float,
    worse_delta: int | float,
) -> FIActionEffectLabel:
    if before is None or after is None:
        return FIActionEffectLabel.NO_CHANGE
    change = after - before
    if change >= abs(improve_delta):
        return FIActionEffectLabel.IMPROVED
    if change <= -abs(worse_delta):
        return FIActionEffectLabel.WORSE
    return FIActionEffectLabel.NO_CHANGE


def _summary_for_label(label: FIActionEffectLabel) -> str:
    if label == FIActionEffectLabel.IMPROVED:
        return "Metrics improved after action."
    if label == FIActionEffectLabel.WORSE:
        return "Metrics worsened after action."
    return "No material change detected."


__all__ = ["build_before_state", "measure_action_effects"]

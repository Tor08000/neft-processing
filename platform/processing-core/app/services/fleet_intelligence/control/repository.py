from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fleet_intelligence import (
    FIDriverDaily,
    FIDriverScore,
    FIStationTrustScore,
    FITrendSnapshot,
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendWindow,
    FIVehicleDaily,
    FIVehicleEfficiencyScore,
)
from app.models.fleet_intelligence_actions import (
    FIActionEffect,
    FIActionEffectLabel,
    FIActionCode,
    FIActionTargetSystem,
    FIAppliedAction,
    FAppliedActionStatus,
    FIInsight,
    FIInsightEntityType,
    FIInsightStatus,
    FIInsightType,
    FISuggestedAction,
    FISuggestedActionStatus,
)


def list_degrading_trends_for_day(db: Session, *, day: date) -> list[FITrendSnapshot]:
    return (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.computed_day == day)
        .filter(FITrendSnapshot.label == FITrendLabel.DEGRADING)
        .all()
    )


def list_trends_window(
    db: Session,
    *,
    entity_type: FITrendEntityType,
    entity_id: str,
    metric: FITrendMetric,
    window: FITrendWindow,
    start_day: date,
    end_day: date,
) -> list[FITrendSnapshot]:
    return (
        db.query(FITrendSnapshot)
        .filter(FITrendSnapshot.entity_type == entity_type)
        .filter(FITrendSnapshot.entity_id == entity_id)
        .filter(FITrendSnapshot.metric == metric)
        .filter(FITrendSnapshot.window == window)
        .filter(FITrendSnapshot.computed_day >= start_day)
        .filter(FITrendSnapshot.computed_day <= end_day)
        .order_by(FITrendSnapshot.computed_day.asc())
        .all()
    )


def get_latest_driver_score(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIDriverScore | None:
    query = (
        db.query(FIDriverScore)
        .filter(FIDriverScore.tenant_id == tenant_id)
        .filter(FIDriverScore.client_id == client_id)
        .filter(FIDriverScore.driver_id == driver_id)
        .filter(FIDriverScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIDriverScore.computed_at <= as_of)
    return query.order_by(FIDriverScore.computed_at.desc()).first()


def get_latest_vehicle_score(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    vehicle_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIVehicleEfficiencyScore | None:
    query = (
        db.query(FIVehicleEfficiencyScore)
        .filter(FIVehicleEfficiencyScore.tenant_id == tenant_id)
        .filter(FIVehicleEfficiencyScore.client_id == client_id)
        .filter(FIVehicleEfficiencyScore.vehicle_id == vehicle_id)
        .filter(FIVehicleEfficiencyScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIVehicleEfficiencyScore.computed_at <= as_of)
    return query.order_by(FIVehicleEfficiencyScore.computed_at.desc()).first()


def get_latest_station_score(
    db: Session,
    *,
    tenant_id: int,
    station_id: str,
    window_days: int,
    as_of: datetime | None = None,
) -> FIStationTrustScore | None:
    query = (
        db.query(FIStationTrustScore)
        .filter(FIStationTrustScore.tenant_id == tenant_id)
        .filter(FIStationTrustScore.station_id == station_id)
        .filter(FIStationTrustScore.window_days == window_days)
    )
    if as_of is not None:
        query = query.filter(FIStationTrustScore.computed_at <= as_of)
    return query.order_by(FIStationTrustScore.computed_at.desc()).first()


def get_insight_for_day(
    db: Session,
    *,
    tenant_id: int,
    insight_type: FIInsightType,
    entity_type: FIInsightEntityType,
    entity_id: str,
    window_days: int,
    day: date,
) -> FIInsight | None:
    return (
        db.query(FIInsight)
        .filter(FIInsight.tenant_id == tenant_id)
        .filter(FIInsight.insight_type == insight_type)
        .filter(FIInsight.entity_type == entity_type)
        .filter(FIInsight.entity_id == entity_id)
        .filter(FIInsight.window_days == window_days)
        .filter(func.date(FIInsight.created_at) == day)
        .one_or_none()
    )


def add_insight(db: Session, insight: FIInsight) -> FIInsight:
    db.add(insight)
    return insight


def list_insights(
    db: Session,
    *,
    client_id: str | None = None,
    status: FIInsightStatus | None = None,
    limit: int = 50,
) -> list[FIInsight]:
    query = db.query(FIInsight)
    if client_id:
        query = query.filter(FIInsight.client_id == client_id)
    if status:
        query = query.filter(FIInsight.status == status)
    return query.order_by(FIInsight.created_at.desc()).limit(limit).all()


def get_insight(db: Session, *, insight_id: str) -> FIInsight | None:
    return db.query(FIInsight).filter(FIInsight.id == insight_id).one_or_none()


def list_suggested_actions(db: Session, *, insight_id: str) -> list[FISuggestedAction]:
    return (
        db.query(FISuggestedAction)
        .filter(FISuggestedAction.insight_id == insight_id)
        .order_by(FISuggestedAction.created_at.asc())
        .all()
    )


def get_suggested_action(db: Session, *, action_id: str) -> FISuggestedAction | None:
    return db.query(FISuggestedAction).filter(FISuggestedAction.id == action_id).one_or_none()


def upsert_suggested_action(db: Session, *, action: FISuggestedAction) -> FISuggestedAction:
    existing = (
        db.query(FISuggestedAction)
        .filter(FISuggestedAction.insight_id == action.insight_id)
        .filter(FISuggestedAction.action_code == action.action_code)
        .one_or_none()
    )
    if existing:
        existing.payload = action.payload
        existing.target_system = action.target_system
        if existing.status == FISuggestedActionStatus.REJECTED:
            existing.status = FISuggestedActionStatus.PROPOSED
        return existing
    db.add(action)
    return action


def add_applied_action(db: Session, applied: FIAppliedAction) -> FIAppliedAction:
    db.add(applied)
    return applied


def list_applied_actions(db: Session, *, insight_id: str) -> list[FIAppliedAction]:
    return (
        db.query(FIAppliedAction)
        .filter(FIAppliedAction.insight_id == insight_id)
        .order_by(FIAppliedAction.applied_at.desc())
        .all()
    )


def get_latest_applied_action(db: Session, *, insight_id: str) -> FIAppliedAction | None:
    return (
        db.query(FIAppliedAction)
        .filter(FIAppliedAction.insight_id == insight_id)
        .order_by(FIAppliedAction.applied_at.desc())
        .first()
    )


def add_action_effect(db: Session, effect: FIActionEffect) -> FIActionEffect:
    db.add(effect)
    return effect


def list_actions_in_monitoring(db: Session, *, cutoff: datetime) -> list[FIAppliedAction]:
    return (
        db.query(FIAppliedAction)
        .join(FIInsight, FIInsight.id == FIAppliedAction.insight_id)
        .filter(FIInsight.status == FIInsightStatus.MONITORING)
        .filter(FIAppliedAction.status == FAppliedActionStatus.SUCCESS)
        .filter(FIAppliedAction.applied_at <= cutoff)
        .all()
    )


def list_action_effects(db: Session, *, applied_action_id: str) -> list[FIActionEffect]:
    return (
        db.query(FIActionEffect)
        .filter(FIActionEffect.applied_action_id == applied_action_id)
        .order_by(FIActionEffect.measured_at.desc())
        .all()
    )


def list_action_effects_for_action_code(
    db: Session,
    *,
    action_code: FIActionCode,
    cutoff: datetime | None = None,
) -> list[FIActionEffect]:
    query = (
        db.query(FIActionEffect)
        .join(FIAppliedAction, FIAppliedAction.id == FIActionEffect.applied_action_id)
        .filter(FIAppliedAction.action_code == action_code)
    )
    if cutoff is not None:
        query = query.filter(FIActionEffect.measured_at >= cutoff)
    return query.order_by(FIActionEffect.measured_at.desc()).all()


def get_latest_effect_label(db: Session, *, insight_id: str) -> FIActionEffectLabel | None:
    effect = (
        db.query(FIActionEffect)
        .join(FIAppliedAction, FIAppliedAction.id == FIActionEffect.applied_action_id)
        .filter(FIAppliedAction.insight_id == insight_id)
        .order_by(FIActionEffect.measured_at.desc())
        .first()
    )
    return effect.effect_label if effect else None


def list_active_insights_before(
    db: Session,
    *,
    cutoff: datetime,
    statuses: set[FIInsightStatus] | None = None,
    client_id: str | None = None,
    limit: int = 200,
) -> list[FIInsight]:
    statuses = statuses or {
        FIInsightStatus.OPEN,
        FIInsightStatus.ACKED,
        FIInsightStatus.ACTION_PLANNED,
        FIInsightStatus.ACTION_APPLIED,
        FIInsightStatus.MONITORING,
    }
    query = db.query(FIInsight).filter(FIInsight.status.in_(statuses)).filter(FIInsight.created_at <= cutoff)
    if client_id:
        query = query.filter(FIInsight.client_id == client_id)
    return query.order_by(FIInsight.created_at.asc()).limit(limit).all()


def count_insight_effects(db: Session, *, insight_id: str) -> int:
    return (
        db.query(func.count(FIActionEffect.id))
        .join(FIAppliedAction, FIAppliedAction.id == FIActionEffect.applied_action_id)
        .filter(FIAppliedAction.insight_id == insight_id)
        .scalar()
        or 0
    )


def action_improvement_counts(
    db: Session, *, action_codes: list[FIActionCode]
) -> dict[FIActionCode, int]:
    if not action_codes:
        return {}
    rows = (
        db.query(FIAppliedAction.action_code, func.count(FIActionEffect.id))
        .join(FIActionEffect, FIActionEffect.applied_action_id == FIAppliedAction.id)
        .filter(FIAppliedAction.action_code.in_(action_codes))
        .filter(FIActionEffect.effect_label == FIActionEffectLabel.IMPROVED)
        .group_by(FIAppliedAction.action_code)
        .all()
    )
    return {action_code: int(count or 0) for action_code, count in rows}


def summarize_driver_anomalies(
    db: Session,
    *,
    tenant_id: int,
    driver_id: str,
    start_day: date,
    end_day: date,
) -> dict[str, int]:
    result = (
        db.query(
            func.coalesce(func.sum(FIDriverDaily.night_fuel_tx_count), 0),
            func.coalesce(func.sum(FIDriverDaily.off_route_fuel_count), 0),
            func.coalesce(func.sum(FIDriverDaily.route_deviation_count), 0),
        )
        .filter(FIDriverDaily.tenant_id == tenant_id)
        .filter(FIDriverDaily.driver_id == driver_id)
        .filter(FIDriverDaily.day >= start_day)
        .filter(FIDriverDaily.day <= end_day)
        .one()
    )
    return {
        "night_fuel": int(result[0] or 0),
        "off_route": int(result[1] or 0),
        "route_deviation": int(result[2] or 0),
    }


def summarize_vehicle_anomalies(
    db: Session,
    *,
    tenant_id: int,
    vehicle_id: str,
    start_day: date,
    end_day: date,
) -> dict[str, int]:
    result = (
        db.query(
            func.coalesce(func.sum(FIVehicleDaily.off_route_count), 0),
            func.coalesce(func.sum(FIVehicleDaily.tank_sanity_exceeded_count), 0),
        )
        .filter(FIVehicleDaily.tenant_id == tenant_id)
        .filter(FIVehicleDaily.vehicle_id == vehicle_id)
        .filter(FIVehicleDaily.day >= start_day)
        .filter(FIVehicleDaily.day <= end_day)
        .one()
    )
    return {
        "off_route": int(result[0] or 0),
        "tank_sanity": int(result[1] or 0),
    }


__all__ = [
    "add_action_effect",
    "add_applied_action",
    "add_insight",
    "action_improvement_counts",
    "count_insight_effects",
    "get_insight",
    "get_insight_for_day",
    "get_latest_applied_action",
    "get_latest_effect_label",
    "get_latest_driver_score",
    "get_latest_station_score",
    "get_latest_vehicle_score",
    "get_suggested_action",
    "list_action_effects",
    "list_action_effects_for_action_code",
    "list_active_insights_before",
    "list_actions_in_monitoring",
    "list_applied_actions",
    "list_degrading_trends_for_day",
    "list_insights",
    "list_suggested_actions",
    "list_trends_window",
    "summarize_driver_anomalies",
    "summarize_vehicle_anomalies",
    "upsert_suggested_action",
]

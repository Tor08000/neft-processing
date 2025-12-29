from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.unified_explain import PrimaryReason
from app.models.fleet_intelligence import FITrendEntityType, FITrendMetric, FITrendWindow
from app.models.fleet_intelligence_actions import (
    FIInsight,
    FIInsightEntityType,
    FIInsightSeverity,
    FIInsightStatus,
    FIInsightType,
)
from app.models.audit_log import ActorType
from app.services.audit_service import AuditService, RequestContext
from app.services.fleet_intelligence.control import defaults, repository


TREND_TO_INSIGHT = {
    FITrendMetric.DRIVER_BEHAVIOR_SCORE: (FIInsightType.DRIVER_BEHAVIOR_DEGRADING, FIInsightEntityType.DRIVER),
    FITrendMetric.STATION_TRUST_SCORE: (FIInsightType.STATION_TRUST_DEGRADING, FIInsightEntityType.STATION),
    FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT: (
        FIInsightType.VEHICLE_EFFICIENCY_DEGRADING,
        FIInsightEntityType.VEHICLE,
    ),
}

INSIGHT_PRIMARY_REASON = {
    FIInsightType.DRIVER_BEHAVIOR_DEGRADING: PrimaryReason.POLICY,
    FIInsightType.STATION_TRUST_DEGRADING: PrimaryReason.LOGISTICS,
    FIInsightType.VEHICLE_EFFICIENCY_DEGRADING: PrimaryReason.POLICY,
}


WINDOW_DAYS_MAP = {
    FITrendWindow.D7: 7,
    FITrendWindow.D30: 30,
    FITrendWindow.ROLLING: 7,
}


def generate_insights_for_day(db: Session, *, day: date) -> list[FIInsight]:
    snapshots = repository.list_degrading_trends_for_day(db, day=day)
    insights: list[FIInsight] = []
    for snapshot in snapshots:
        mapping = TREND_TO_INSIGHT.get(snapshot.metric)
        if not mapping:
            continue
        insight_type, entity_type = mapping
        window_days = WINDOW_DAYS_MAP.get(snapshot.window, 7)
        consecutive_days = _count_consecutive_degrading(
            db,
            day=day,
            entity_type=snapshot.entity_type,
            entity_id=str(snapshot.entity_id),
            metric=snapshot.metric,
            window=snapshot.window,
        )
        if consecutive_days < defaults.INSIGHT_THRESHOLDS.degrading_days_medium:
            continue

        severity = _resolve_severity(
            db,
            tenant_id=snapshot.tenant_id,
            client_id=snapshot.client_id or "",
            entity_type=entity_type,
            entity_id=str(snapshot.entity_id),
            window_days=window_days,
            consecutive_days=consecutive_days,
        )
        summary = _build_summary(insight_type=insight_type, consecutive_days=consecutive_days, severity=severity)
        evidence = {
            "trend_snapshot_id": str(snapshot.id),
            "trend_label": snapshot.label.value,
            "consecutive_days": consecutive_days,
            "metric": snapshot.metric.value,
            "window": snapshot.window.value,
            "current_value": snapshot.current_value,
            "baseline_value": snapshot.baseline_value,
            "delta": snapshot.delta,
        }
        existing = repository.get_insight_for_day(
            db,
            tenant_id=snapshot.tenant_id,
            insight_type=insight_type,
            entity_type=entity_type,
            entity_id=str(snapshot.entity_id),
            window_days=window_days,
            day=day,
        )
        if existing:
            existing.severity = severity
            existing.summary = summary
            existing.evidence = evidence
            insights.append(existing)
            continue

        insight = FIInsight(
            tenant_id=snapshot.tenant_id,
            client_id=snapshot.client_id or "",
            insight_type=insight_type,
            entity_type=entity_type,
            entity_id=str(snapshot.entity_id),
            window_days=window_days,
            severity=severity,
            status=FIInsightStatus.OPEN,
            primary_reason=INSIGHT_PRIMARY_REASON.get(insight_type, PrimaryReason.UNKNOWN),
            summary=summary,
            evidence=evidence,
        )
        repository.add_insight(db, insight)
        insights.append(insight)
        _audit_insight_created(db, insight)

    return insights


def _count_consecutive_degrading(
    db: Session,
    *,
    day: date,
    entity_type: FITrendEntityType,
    entity_id: str,
    metric: FITrendMetric,
    window: FITrendWindow,
) -> int:
    start_day = day - timedelta(days=defaults.INSIGHT_THRESHOLDS.degrading_days_high - 1)
    snapshots = repository.list_trends_window(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        metric=metric,
        window=window,
        start_day=start_day,
        end_day=day,
    )
    labels_by_day = {snap.computed_day: snap.label for snap in snapshots}
    count = 0
    cursor = day
    while cursor >= start_day:
        label = labels_by_day.get(cursor)
        if label is None or label.value != "DEGRADING":
            break
        count += 1
        cursor -= timedelta(days=1)
    return count


def _resolve_severity(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    entity_type: FIInsightEntityType,
    entity_id: str,
    window_days: int,
    consecutive_days: int,
) -> FIInsightSeverity:
    thresholds = defaults.INSIGHT_THRESHOLDS
    severity = FIInsightSeverity.MEDIUM
    if consecutive_days >= thresholds.degrading_days_high:
        severity = FIInsightSeverity.HIGH

    if entity_type == FIInsightEntityType.DRIVER:
        score = repository.get_latest_driver_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            driver_id=entity_id,
            window_days=window_days,
        )
        if score:
            if score.score >= thresholds.driver_score_critical:
                return FIInsightSeverity.CRITICAL
            if score.score >= thresholds.driver_score_high:
                return FIInsightSeverity.HIGH
    if entity_type == FIInsightEntityType.STATION:
        score = repository.get_latest_station_score(
            db,
            tenant_id=tenant_id,
            station_id=entity_id,
            window_days=window_days,
        )
        if score:
            if score.trust_score <= thresholds.station_score_critical:
                return FIInsightSeverity.CRITICAL
            if score.trust_score <= thresholds.station_score_high:
                return FIInsightSeverity.HIGH
    if entity_type == FIInsightEntityType.VEHICLE:
        score = repository.get_latest_vehicle_score(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            vehicle_id=entity_id,
            window_days=window_days,
        )
        if score and score.efficiency_score is not None:
            if score.efficiency_score <= thresholds.vehicle_efficiency_critical:
                return FIInsightSeverity.CRITICAL
            if score.efficiency_score <= thresholds.vehicle_efficiency_high:
                return FIInsightSeverity.HIGH

    return severity


def _build_summary(
    *,
    insight_type: FIInsightType,
    consecutive_days: int,
    severity: FIInsightSeverity,
) -> str:
    return (
        f"{insight_type.value.replace('_', ' ').title()}: "
        f"{consecutive_days} day(s) degrading, severity {severity.value}."
    )


def _audit_insight_created(db: Session, insight: FIInsight) -> None:
    audit = AuditService(db)
    audit.audit(
        event_type="FI_INSIGHT_CREATED",
        entity_type="fi_insight",
        entity_id=str(insight.id),
        action="CREATE",
        after=_audit_payload(insight),
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, tenant_id=insight.tenant_id),
    )


def _audit_payload(insight: FIInsight) -> dict[str, Any]:
    return {
        "insight_id": str(insight.id),
        "insight_type": insight.insight_type.value,
        "entity_type": insight.entity_type.value,
        "entity_id": str(insight.entity_id),
        "status": insight.status.value,
        "severity": insight.severity.value,
        "summary": insight.summary,
        "window_days": insight.window_days,
    }


__all__ = ["generate_insights_for_day"]

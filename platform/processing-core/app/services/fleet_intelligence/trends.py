from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import median
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.crm import CRMClient
from app.models.fleet_intelligence import (
    FIDriverScore,
    FIStationTrustScore,
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FITrendWindow,
    FIVehicleEfficiencyScore,
)
from app.services.fleet_intelligence import explain, repository
from app.services.fleet_intelligence.defaults import FI_TREND_THRESHOLDS


@dataclass(frozen=True)
class TrendLabelResult:
    label: FITrendLabel
    delta: float | None


def compute_trends_for_client(db: Session, *, client_id: str, day: date) -> dict[str, int]:
    client = db.get(CRMClient, client_id)
    if not client:
        return {"drivers": 0, "vehicles": 0, "stations": 0}
    tenant_id = client.tenant_id
    computed_at = datetime.combine(day, time.min).replace(tzinfo=timezone.utc)
    as_of = datetime.combine(day, time.max).replace(tzinfo=timezone.utc)

    created = {
        "drivers": _compute_driver_trends(db, tenant_id=tenant_id, client_id=client_id, computed_at=computed_at, as_of=as_of),
        "vehicles": _compute_vehicle_trends(db, tenant_id=tenant_id, client_id=client_id, computed_at=computed_at, as_of=as_of),
        "stations": _compute_station_trends(db, tenant_id=tenant_id, client_id=client_id, computed_at=computed_at, as_of=as_of),
    }
    return created


def compute_trends_all(db: Session, *, day: date) -> dict[str, int]:
    totals = {"clients": 0, "drivers": 0, "vehicles": 0, "stations": 0}
    clients = db.query(CRMClient).all()
    for client in clients:
        totals["clients"] += 1
        result = compute_trends_for_client(db, client_id=client.id, day=day)
        totals["drivers"] += result["drivers"]
        totals["vehicles"] += result["vehicles"]
        totals["stations"] += result["stations"]
    return totals


def summarize_trend_snapshot(snapshot: FITrendSnapshot) -> str | None:
    if not snapshot.explain:
        return None
    if snapshot.metric == FITrendMetric.DRIVER_BEHAVIOR_SCORE:
        top_factors = snapshot.explain.get("top_factors") if isinstance(snapshot.explain, dict) else None
        if not isinstance(top_factors, list):
            return None
        return explain.build_driver_summary(top_factors=top_factors)
    if snapshot.metric == FITrendMetric.STATION_TRUST_SCORE:
        reasons = snapshot.explain.get("reasons") if isinstance(snapshot.explain, dict) else None
        if not isinstance(reasons, list):
            return None
        return ", ".join(reasons) if reasons else "Нет причин деградации"
    if snapshot.metric == FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT:
        return explain.build_vehicle_summary(delta_pct=snapshot.current_value, window_days=None)
    return None


def _compute_driver_trends(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    computed_at: datetime,
    as_of: datetime,
) -> int:
    created = 0
    current_scores = repository.list_latest_driver_scores_by_client(
        db,
        client_id=client_id,
        window_days=7,
        as_of=as_of,
    )
    baseline_scores = repository.list_latest_driver_scores_by_client(
        db,
        client_id=client_id,
        window_days=30,
        as_of=as_of,
    )
    baseline_map = {str(score.driver_id): score for score in baseline_scores}
    for score in current_scores:
        baseline = baseline_map.get(str(score.driver_id))
        payload = _build_driver_snapshot(
            tenant_id=tenant_id,
            client_id=client_id,
            current=score,
            baseline=baseline,
            computed_at=computed_at,
        )
        repository.upsert_trend_snapshot(db, payload)
        created += 1
    return created


def _compute_station_trends(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    computed_at: datetime,
    as_of: datetime,
) -> int:
    created = 0
    current_scores = repository.list_latest_station_scores_by_tenant(
        db,
        tenant_id=tenant_id,
        window_days=30,
        as_of=as_of,
    )
    baseline_cutoff = as_of - timedelta(days=30)
    for score in current_scores:
        baseline = repository.get_latest_station_score(
            db,
            tenant_id=tenant_id,
            station_id=str(score.station_id),
            window_days=30,
            as_of=baseline_cutoff,
        )
        payload = _build_station_snapshot(
            tenant_id=tenant_id,
            client_id=client_id,
            current=score,
            baseline=baseline,
            computed_at=computed_at,
        )
        repository.upsert_trend_snapshot(db, payload)
        created += 1
    return created


def _compute_vehicle_trends(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    computed_at: datetime,
    as_of: datetime,
) -> int:
    created = 0
    current_scores = repository.list_latest_vehicle_scores_by_client(
        db,
        client_id=client_id,
        window_days=7,
        as_of=as_of,
    )
    baseline_start = as_of - timedelta(days=30)
    for score in current_scores:
        baseline_values = repository.list_vehicle_scores_window(
            db,
            client_id=client_id,
            vehicle_id=str(score.vehicle_id),
            window_days=7,
            start_at=baseline_start,
            end_at=as_of,
        )
        baseline_values = [value for value in baseline_values if value.computed_at < score.computed_at]
        payload = _build_vehicle_snapshot(
            tenant_id=tenant_id,
            client_id=client_id,
            current=score,
            baseline_values=baseline_values,
            computed_at=computed_at,
        )
        repository.upsert_trend_snapshot(db, payload)
        created += 1
    return created


def _build_driver_snapshot(
    *,
    tenant_id: int,
    client_id: str,
    current: FIDriverScore,
    baseline: FIDriverScore | None,
    computed_at: datetime,
) -> dict:
    current_value = float(current.score) if current.score is not None else None
    baseline_value = float(baseline.score) if baseline else None
    label_result = _label_for_metric(
        metric_key="driver_score",
        delta=_delta(current_value, baseline_value),
    )
    top_factors = _extract_driver_factors(current)
    explain_payload = explain.build_driver_trend_explain(top_factors=top_factors)
    return _build_snapshot_payload(
        tenant_id=tenant_id,
        client_id=client_id,
        entity_type=FITrendEntityType.DRIVER,
        entity_id=str(current.driver_id),
        metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
        window=FITrendWindow.D7,
        current_value=current_value,
        baseline_value=baseline_value,
        label_result=label_result,
        computed_at=computed_at,
        explain_payload=explain_payload,
    )


def _build_station_snapshot(
    *,
    tenant_id: int,
    client_id: str,
    current: FIStationTrustScore,
    baseline: FIStationTrustScore | None,
    computed_at: datetime,
) -> dict:
    current_value = float(current.trust_score) if current.trust_score is not None else None
    baseline_value = float(baseline.trust_score) if baseline else None
    label_result = _label_for_metric(
        metric_key="station_trust",
        delta=_delta(current_value, baseline_value),
    )
    reasons = _extract_station_reasons(current)
    explain_payload = explain.build_station_trend_explain(reasons=reasons)
    return _build_snapshot_payload(
        tenant_id=tenant_id,
        client_id=client_id,
        entity_type=FITrendEntityType.STATION,
        entity_id=str(current.station_id),
        metric=FITrendMetric.STATION_TRUST_SCORE,
        window=FITrendWindow.D30,
        current_value=current_value,
        baseline_value=baseline_value,
        label_result=label_result,
        computed_at=computed_at,
        explain_payload=explain_payload,
    )


def _build_vehicle_snapshot(
    *,
    tenant_id: int,
    client_id: str,
    current: FIVehicleEfficiencyScore,
    baseline_values: Iterable[FIVehicleEfficiencyScore],
    computed_at: datetime,
) -> dict:
    current_value = float(current.delta_pct) if current.delta_pct is not None else None
    baseline_value = _median_value([score.delta_pct for score in baseline_values])
    label_result = _label_for_metric(
        metric_key="vehicle_eff_delta_pct",
        delta=_delta(current_value, baseline_value),
        normalize_vehicle_pct=True,
    )
    explain_payload = explain.build_vehicle_trend_explain(
        delta_pct=current.delta_pct,
        baseline_ml_per_100km=current.baseline_ml_per_100km,
        actual_ml_per_100km=current.actual_ml_per_100km,
    )
    return _build_snapshot_payload(
        tenant_id=tenant_id,
        client_id=client_id,
        entity_type=FITrendEntityType.VEHICLE,
        entity_id=str(current.vehicle_id),
        metric=FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT,
        window=FITrendWindow.ROLLING,
        current_value=current_value,
        baseline_value=baseline_value,
        label_result=label_result,
        computed_at=computed_at,
        explain_payload=explain_payload,
    )


def _build_snapshot_payload(
    *,
    tenant_id: int,
    client_id: str,
    entity_type: FITrendEntityType,
    entity_id: str,
    metric: FITrendMetric,
    window: FITrendWindow,
    current_value: float | None,
    baseline_value: float | None,
    label_result: TrendLabelResult,
    computed_at: datetime,
    explain_payload: dict,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metric": metric,
        "window": window,
        "current_value": current_value,
        "baseline_value": baseline_value,
        "delta": label_result.delta,
        "delta_pct": _delta_pct(label_result.delta, baseline_value),
        "label": label_result.label,
        "computed_day": computed_at.date(),
        "computed_at": computed_at,
        "explain": explain_payload,
    }


def _label_for_metric(
    *,
    metric_key: str,
    delta: float | None,
    normalize_vehicle_pct: bool = False,
) -> TrendLabelResult:
    if delta is None:
        return TrendLabelResult(label=FITrendLabel.UNKNOWN, delta=None)
    thresholds = FI_TREND_THRESHOLDS[metric_key]
    stable = thresholds["stable"]
    degrading = thresholds["degrading"]
    compare_delta = delta * 100 if normalize_vehicle_pct else delta

    if metric_key == "station_trust":
        if compare_delta <= -degrading:
            label = FITrendLabel.DEGRADING
        elif abs(compare_delta) <= stable:
            label = FITrendLabel.STABLE
        elif compare_delta >= degrading:
            label = FITrendLabel.IMPROVING
        else:
            label = FITrendLabel.STABLE
    else:
        if compare_delta >= degrading:
            label = FITrendLabel.DEGRADING
        elif abs(compare_delta) <= stable:
            label = FITrendLabel.STABLE
        elif compare_delta <= -degrading:
            label = FITrendLabel.IMPROVING
        else:
            label = FITrendLabel.STABLE

    return TrendLabelResult(label=label, delta=delta)


def _extract_driver_factors(score: FIDriverScore) -> list[dict]:
    explain_payload = score.explain or {}
    driver_payload = explain_payload.get("driver_behavior") if isinstance(explain_payload, dict) else None
    top_factors = driver_payload.get("top_factors") if isinstance(driver_payload, dict) else None
    if not isinstance(top_factors, list):
        return []
    return top_factors[:2]


def _extract_station_reasons(score: FIStationTrustScore) -> list[str]:
    explain_payload = score.explain or {}
    station_payload = explain_payload.get("station_trust") if isinstance(explain_payload, dict) else None
    reasons = station_payload.get("reasons") if isinstance(station_payload, dict) else None
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons[:2]]


def _median_value(values: Iterable[float | None]) -> float | None:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return float(median(cleaned))


def _delta(current_value: float | None, baseline_value: float | None) -> float | None:
    if current_value is None or baseline_value is None:
        return None
    return current_value - baseline_value


def _delta_pct(delta_value: float | None, baseline_value: float | None) -> float | None:
    if delta_value is None or baseline_value in (None, 0):
        return None
    return (delta_value / baseline_value) * 100


__all__ = ["compute_trends_for_client", "compute_trends_all", "summarize_trend_snapshot"]

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.fleet_intelligence import FIDriverDaily, FIStationDaily, FIVehicleDaily
from app.services.fleet_intelligence import aggregates, explain, repository, scores
from app.services.fleet_intelligence.defaults import VEHICLE_BASELINE_DAYS


def run_daily_aggregates(db: Session, *, day: date) -> dict[str, list]:
    result = aggregates.compute_daily_aggregates(db, day=day)
    db.commit()
    return result


def run_scores(db: Session, *, as_of: date, windows: Iterable[int] = (7, 30)) -> dict[str, int]:
    computed_at = datetime.utcnow()
    created = {"drivers": 0, "vehicles": 0, "stations": 0}
    for window_days in windows:
        start_day = as_of - timedelta(days=window_days - 1)
        created["drivers"] += _compute_driver_scores(
            db, start_day=start_day, end_day=as_of, window_days=window_days, computed_at=computed_at
        )
        created["vehicles"] += _compute_vehicle_scores(
            db, start_day=start_day, end_day=as_of, window_days=window_days, computed_at=computed_at
        )
        created["stations"] += _compute_station_scores(
            db, start_day=start_day, end_day=as_of, window_days=window_days, computed_at=computed_at
        )
    db.commit()
    return created


def _compute_driver_scores(
    db: Session,
    *,
    start_day: date,
    end_day: date,
    window_days: int,
    computed_at: datetime,
) -> int:
    driver_keys = (
        db.query(FIDriverDaily.tenant_id, FIDriverDaily.driver_id)
        .filter(FIDriverDaily.day >= start_day)
        .filter(FIDriverDaily.day <= end_day)
        .distinct()
        .all()
    )
    created = 0
    for tenant_id, driver_id in driver_keys:
        daily = repository.list_driver_daily_window(
            db,
            tenant_id=tenant_id,
            driver_id=str(driver_id),
            start_day=start_day,
            end_day=end_day,
        )
        if not daily:
            continue
        client_id = daily[0].client_id
        totals = _sum_driver_daily(daily)
        result = scores.compute_driver_behavior_score(
            scores.DriverScoreInputs(
                off_route_fuel_count=totals["off_route_fuel_count"],
                night_fuel_tx_count=totals["night_fuel_tx_count"],
                route_deviation_count=totals["route_deviation_count"],
                risk_block_count=totals["risk_block_count"],
                review_required_count=totals["review_required_count"],
                tx_count=totals["fuel_tx_count"],
            )
        )
        top_factors = _top_driver_factors(result.contributions)
        explain_payload = explain.build_driver_explain(score=result.score, level=result.level, top_factors=top_factors)
        repository.create_driver_score(
            db,
            {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "driver_id": str(driver_id),
                "computed_at": computed_at,
                "window_days": window_days,
                "score": result.score,
                "level": result.level,
                "explain": explain_payload,
            },
        )
        created += 1
    return created


def _compute_vehicle_scores(
    db: Session,
    *,
    start_day: date,
    end_day: date,
    window_days: int,
    computed_at: datetime,
) -> int:
    vehicle_keys = (
        db.query(FIVehicleDaily.tenant_id, FIVehicleDaily.vehicle_id)
        .filter(FIVehicleDaily.day >= start_day)
        .filter(FIVehicleDaily.day <= end_day)
        .distinct()
        .all()
    )
    baseline_start = end_day - timedelta(days=VEHICLE_BASELINE_DAYS - 1)
    created = 0
    for tenant_id, vehicle_id in vehicle_keys:
        daily = repository.list_vehicle_daily_window(
            db,
            tenant_id=tenant_id,
            vehicle_id=str(vehicle_id),
            start_day=start_day,
            end_day=end_day,
        )
        if not daily:
            continue
        client_id = daily[0].client_id
        baseline_daily = repository.list_vehicle_daily_window(
            db,
            tenant_id=tenant_id,
            vehicle_id=str(vehicle_id),
            start_day=baseline_start,
            end_day=end_day,
        )
        result = scores.compute_vehicle_efficiency_score(
            window_days=window_days,
            daily_values=[record.fuel_per_100km_ml for record in daily],
            baseline_values=[record.fuel_per_100km_ml for record in baseline_daily],
            baseline_days=VEHICLE_BASELINE_DAYS,
        )
        if result.efficiency_score is None or result.delta_pct is None:
            explain_payload = explain.build_vehicle_no_distance_explain()
        else:
            explain_payload = explain.build_vehicle_explain(
                efficiency_score=result.efficiency_score,
                baseline_ml_per_100km=result.baseline_ml_per_100km or 0.0,
                actual_ml_per_100km=result.actual_ml_per_100km or 0.0,
                delta_pct=result.delta_pct,
            )
        repository.create_vehicle_score(
            db,
            {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "vehicle_id": str(vehicle_id),
                "computed_at": computed_at,
                "window_days": window_days,
                "efficiency_score": result.efficiency_score,
                "baseline_ml_per_100km": result.baseline_ml_per_100km,
                "actual_ml_per_100km": result.actual_ml_per_100km,
                "delta_pct": result.delta_pct,
                "explain": explain_payload,
            },
        )
        created += 1
    return created


def _compute_station_scores(
    db: Session,
    *,
    start_day: date,
    end_day: date,
    window_days: int,
    computed_at: datetime,
) -> int:
    station_keys = (
        db.query(FIStationDaily.tenant_id, FIStationDaily.station_id)
        .filter(FIStationDaily.day >= start_day)
        .filter(FIStationDaily.day <= end_day)
        .distinct()
        .all()
    )
    created = 0
    for tenant_id, station_id in station_keys:
        daily = repository.list_station_daily_window(
            db,
            tenant_id=tenant_id,
            station_id=str(station_id),
            start_day=start_day,
            end_day=end_day,
        )
        if not daily:
            continue
        tenant_id = daily[0].tenant_id
        network_id = daily[0].network_id
        totals = _sum_station_daily(daily)
        network_avg_volume = repository.list_station_network_avg_volume(
            db,
            tenant_id=tenant_id,
            network_id=network_id,
            start_day=start_day,
            end_day=end_day,
        )
        result = scores.compute_station_trust_score(
            scores.StationTrustInputs(
                tx_count=totals["tx_count"],
                risk_block_count=totals["risk_block_count"],
                decline_count=totals["decline_count"],
                burst_events_count=totals["burst_events_count"],
                outlier_score=totals["outlier_score"],
                avg_volume_ml=totals["avg_volume_ml"],
                network_avg_volume_ml=network_avg_volume,
            )
        )
        reasons = _station_reasons(result.penalties)
        explain_payload = explain.build_station_explain(
            trust_score=result.trust_score,
            level=result.level,
            reasons=reasons,
        )
        repository.create_station_score(
            db,
            {
                "tenant_id": tenant_id,
                "station_id": str(station_id),
                "network_id": network_id,
                "computed_at": computed_at,
                "window_days": window_days,
                "trust_score": result.trust_score,
                "level": result.level,
                "explain": explain_payload,
            },
        )
        created += 1
    return created


def _sum_driver_daily(records: Iterable) -> dict[str, int]:
    totals = defaultdict(int)
    for record in records:
        totals["fuel_tx_count"] += record.fuel_tx_count
        totals["night_fuel_tx_count"] += record.night_fuel_tx_count
        totals["off_route_fuel_count"] += record.off_route_fuel_count
        totals["route_deviation_count"] += record.route_deviation_count
        totals["review_required_count"] += record.review_required_count
        totals["risk_block_count"] += record.risk_block_count
    return totals


def _sum_station_daily(records: Iterable) -> dict[str, float]:
    totals = defaultdict(float)
    for record in records:
        totals["tx_count"] += record.tx_count
        totals["risk_block_count"] += record.risk_block_count
        totals["decline_count"] += record.decline_count
        totals["burst_events_count"] += record.burst_events_count
        if record.outlier_score is not None:
            totals["outlier_score"] = max(totals.get("outlier_score", 0.0), record.outlier_score)
        if record.avg_volume_ml is not None:
            totals["volume_weighted_sum"] += record.avg_volume_ml * record.tx_count
    if totals["tx_count"]:
        totals["avg_volume_ml"] = totals["volume_weighted_sum"] / totals["tx_count"]
    else:
        totals["avg_volume_ml"] = None
    return totals


def _top_driver_factors(contributions: dict[str, float]) -> list[dict]:
    sorted_items = sorted(contributions.items(), key=lambda item: item[1], reverse=True)
    top_factors = []
    for factor, value in sorted_items[:3]:
        impact = "high" if value >= 15 else "medium" if value >= 8 else "low"
        top_factors.append({"factor": factor, "value": value, "impact": impact})
    return top_factors


def _station_reasons(penalties: dict[str, float]) -> list[str]:
    if not penalties:
        return []
    sorted_items = sorted(penalties.items(), key=lambda item: item[1], reverse=True)
    reasons = []
    for factor, value in sorted_items[:3]:
        if factor == "risk_block_rate":
            reasons.append("High risk block rate")
        elif factor == "decline_rate":
            reasons.append("Elevated decline rate")
        elif factor == "burst_events":
            reasons.append("Burst transaction pattern")
        elif factor == "outlier_score":
            reasons.append("Outlier score indicates anomalies")
        elif factor == "avg_volume_deviation":
            reasons.append("Average volume deviates from network")
        else:
            reasons.append(f"{factor} penalty")
    return reasons


__all__ = ["run_daily_aggregates", "run_scores"]

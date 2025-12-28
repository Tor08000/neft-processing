from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.logistics import (
    LogisticsNavigatorExplain,
    LogisticsNavigatorExplainType,
    LogisticsRouteSnapshot,
)
from app.services.logistics.navigator.base import DeviationScore, GeoPoint
from app.services.logistics.navigator.registry import get, is_enabled


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_geometry(points: Iterable[GeoPoint]) -> list[dict[str, float]]:
    return [{"lat": point.lat, "lon": point.lon} for point in points]


def create_route_snapshot(
    db: Session,
    *,
    order_id: str,
    route_id: str,
    stops: list[GeoPoint],
    provider: str | None = None,
) -> LogisticsRouteSnapshot | None:
    if not is_enabled():
        return None
    if len(stops) < 2:
        return None
    adapter = get(provider)
    route = adapter.build_route(stops)
    eta_result = adapter.estimate_eta(route)

    snapshot = LogisticsRouteSnapshot(
        order_id=order_id,
        route_id=route_id,
        provider=route.provider,
        geometry=_serialize_geometry(route.geometry),
        distance_km=round(route.distance_km, 3),
        eta_minutes=eta_result.eta_minutes,
        created_at=_now(),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    create_eta_explain(db, route_snapshot=snapshot, eta_result=eta_result)
    return snapshot


def create_eta_explain(
    db: Session,
    *,
    route_snapshot: LogisticsRouteSnapshot,
    eta_result,
) -> LogisticsNavigatorExplain:
    payload = {
        "navigator": route_snapshot.provider,
        "method": eta_result.method,
        "distance_km": route_snapshot.distance_km,
        "eta_minutes": eta_result.eta_minutes,
        "assumptions": eta_result.assumptions,
    }
    explain = LogisticsNavigatorExplain(
        route_snapshot_id=str(route_snapshot.id),
        type=LogisticsNavigatorExplainType.ETA,
        payload=payload,
        created_at=_now(),
    )
    db.add(explain)
    db.commit()
    db.refresh(explain)
    return explain


def create_deviation_explain(
    db: Session,
    *,
    route_snapshot: LogisticsRouteSnapshot,
    deviation_score: DeviationScore,
) -> LogisticsNavigatorExplain:
    payload = {
        "expected_distance": deviation_score.expected_distance_km,
        "actual_distance": deviation_score.actual_distance_km,
        "delta_pct": deviation_score.delta_pct,
        "score": deviation_score.score,
        "reason": deviation_score.reason,
    }
    explain = LogisticsNavigatorExplain(
        route_snapshot_id=str(route_snapshot.id),
        type=LogisticsNavigatorExplainType.DEVIATION,
        payload=payload,
        created_at=_now(),
    )
    db.add(explain)
    db.commit()
    db.refresh(explain)
    return explain

from __future__ import annotations

import os
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
from app.services.logistics.repository import get_order, refresh_by_id
from app.services.logistics.service_client import LogisticsServiceClient, RoutePreviewResult


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
    # Materialize a local snapshot/evidence artifact inside processing-core.
    # This does not make processing-core the owner of external routing transport.
    if not is_enabled():
        return None
    if len(stops) < 2:
        return None
    preview_error: str | None = None
    if _should_use_service_preview(provider):
        try:
            preview = LogisticsServiceClient().preview_route(
                _build_preview_payload(db, order_id=order_id, route_id=route_id, stops=stops)
            )
            return _persist_preview_snapshot(
                db,
                order_id=order_id,
                route_id=route_id,
                preview=preview,
            )
        except RuntimeError as exc:
            preview_error = str(exc)
    adapter = get(provider)
    route = adapter.build_route(stops)
    eta_result = adapter.estimate_eta(route)
    if preview_error:
        eta_result = _with_assumption(eta_result, f"preview_fallback={preview_error}")

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
    db.flush()
    snapshot_id = str(snapshot.id)
    db.commit()
    snapshot = refresh_by_id(db, snapshot, LogisticsRouteSnapshot, snapshot_id)

    create_eta_explain(db, route_snapshot=snapshot, eta_result=eta_result)
    return snapshot


def _should_use_service_preview(explicit_provider: str | None) -> bool:
    if explicit_provider:
        return False
    return os.getenv("LOGISTICS_SERVICE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}


def _build_preview_payload(
    db: Session,
    *,
    order_id: str,
    route_id: str,
    stops: list[GeoPoint],
) -> dict[str, object]:
    order = get_order(db, order_id=order_id)
    order_meta = order.meta if order and isinstance(order.meta, dict) else {}
    return {
        "route_id": route_id,
        "points": [
            {"lat": stop.lat, "lon": stop.lon, "sequence": idx}
            for idx, stop in enumerate(stops)
        ],
        "vehicle": {
            "type": order_meta.get("vehicle_type", "truck"),
            "fuel_type": order_meta.get("fuel_type", "diesel"),
        },
        "context": {},
    }


def _persist_preview_snapshot(
    db: Session,
    *,
    order_id: str,
    route_id: str,
    preview: RoutePreviewResult,
) -> LogisticsRouteSnapshot:
    snapshot = LogisticsRouteSnapshot(
        order_id=order_id,
        route_id=route_id,
        provider=preview.provider,
        geometry=_serialize_geometry(preview.geometry),
        distance_km=round(preview.distance_km, 3),
        eta_minutes=preview.eta_minutes,
        created_at=_now(),
    )
    db.add(snapshot)
    db.flush()
    snapshot_id = str(snapshot.id)
    db.commit()
    snapshot = refresh_by_id(db, snapshot, LogisticsRouteSnapshot, snapshot_id)

    create_eta_explain(db, route_snapshot=snapshot, eta_result=_eta_result_from_preview(preview))
    return snapshot


def _eta_result_from_preview(preview: RoutePreviewResult):
    assumptions = [
        "external_preview",
        f"compute_provider={preview.provider}",
        f"confidence={round(preview.confidence, 3)}",
    ]
    if preview.degraded:
        assumptions.append("degraded=true")
    if preview.degradation_reason:
        assumptions.append(f"degradation_reason={preview.degradation_reason}")
    return _with_eta_result(
        eta_minutes=preview.eta_minutes,
        assumptions=assumptions,
        method="service_preview",
    )


def _with_assumption(eta_result, assumption: str):
    return _with_eta_result(
        eta_minutes=eta_result.eta_minutes,
        assumptions=[*eta_result.assumptions, assumption],
        method=eta_result.method,
    )


def _with_eta_result(*, eta_minutes: int, assumptions: list[str], method: str):
    from app.services.logistics.navigator.base import ETAResult

    return ETAResult(
        eta_minutes=eta_minutes,
        assumptions=assumptions,
        method=method,
    )


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
    db.flush()
    explain_id = str(explain.id)
    db.commit()
    explain = refresh_by_id(db, explain, LogisticsNavigatorExplain, explain_id)
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
    db.flush()
    explain_id = str(explain.id)
    db.commit()
    explain = refresh_by_id(db, explain, LogisticsNavigatorExplain, explain_id)
    return explain

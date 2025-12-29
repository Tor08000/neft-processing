from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.fleet_intelligence import (
    FIDriverScore,
    FIStationTrustScore,
    FIVehicleEfficiencyScore,
)
from app.services.fleet_intelligence import explain
from app.services.fleet_intelligence.defaults import FI_THRESHOLDS
from app.services.fleet_intelligence.taxonomy import ActionHintCode, InsightType


@dataclass(frozen=True)
class _InsightCandidate:
    payload: dict
    required_count: int
    level_rank: int
    magnitude: float
    entity_id: str


_LEVEL_RANK = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "VERY_HIGH": 3,
}


_ACTION_TITLES = {
    ActionHintCode.RESTRICT_NIGHT_FUELING: "Ограничить ночные заправки",
    ActionHintCode.REQUIRE_ROUTE_LINKED_REFUEL: "Разрешать заправку только на точках маршрута",
    ActionHintCode.REVIEW_DRIVER_BEHAVIOR: "Провести проверку поведения водителя",
    ActionHintCode.CHECK_VEHICLE_FUEL_EFFICIENCY: "Проверить топливную эффективность автомобиля",
    ActionHintCode.EXCLUDE_STATION_FROM_ROUTES: "Исключить станцию из маршрутов",
    ActionHintCode.MOVE_STATION_TO_WATCHLIST: "Перевести станцию в список наблюдения",
    ActionHintCode.REQUEST_COMPLIANCE_REVIEW: "Запросить проверку комплаенса",
}


def build_fleet_insight_payload(
    *,
    driver_scores: Iterable[FIDriverScore] = (),
    vehicle_scores: Iterable[FIVehicleEfficiencyScore] = (),
    station_scores: Iterable[FIStationTrustScore] = (),
) -> dict | None:
    candidates: list[_InsightCandidate] = []
    for driver in driver_scores:
        candidate = _driver_candidate(driver)
        if candidate:
            candidates.append(candidate)
    for vehicle in vehicle_scores:
        candidate = _vehicle_candidate(vehicle)
        if candidate:
            candidates.append(candidate)
    for station in station_scores:
        candidate = _station_candidate(station)
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return None

    candidates_sorted = sorted(candidates, key=_sort_key)
    primary = candidates_sorted[0]
    secondary = [candidate.payload for candidate in candidates_sorted[1:]]
    return {
        "primary_insight": primary.payload,
        "secondary_insights": secondary,
    }


def _driver_candidate(score: FIDriverScore) -> _InsightCandidate | None:
    thresholds = FI_THRESHOLDS["driver"]
    if score.score < thresholds["high"]:
        return None
    actions = [
        _action(ActionHintCode.REVIEW_DRIVER_BEHAVIOR, severity="REQUIRED"),
    ]
    level = "HIGH"
    if score.score >= thresholds["very_high"]:
        actions.append(_action(ActionHintCode.RESTRICT_NIGHT_FUELING, severity="REQUIRED"))
        actions.append(_action(ActionHintCode.REQUIRE_ROUTE_LINKED_REFUEL, severity="INFO"))
        level = "VERY_HIGH"
    payload = {
        "type": InsightType.DRIVER_BEHAVIOR.value,
        "entity_id": str(score.driver_id),
        "level": level,
        "score": score.score,
        "summary": explain.build_driver_summary(top_factors=_driver_top_factors(score)),
        "actions": _dedupe_actions(actions),
    }
    return _build_candidate(payload, magnitude=float(score.score))


def _vehicle_candidate(score: FIVehicleEfficiencyScore) -> _InsightCandidate | None:
    if score.delta_pct is None:
        return None
    delta_pct = score.delta_pct * 100
    thresholds = FI_THRESHOLDS["vehicle_efficiency_delta_pct"]
    if delta_pct < thresholds["warn"]:
        return None
    severity = "INFO"
    level = "HIGH"
    if delta_pct >= thresholds["high"]:
        severity = "REQUIRED"
        level = "VERY_HIGH"
    actions = [_action(ActionHintCode.CHECK_VEHICLE_FUEL_EFFICIENCY, severity=severity)]
    payload = {
        "type": InsightType.VEHICLE_EFFICIENCY.value,
        "entity_id": str(score.vehicle_id),
        "level": level,
        "score": int(round(delta_pct)),
        "summary": explain.build_vehicle_summary(delta_pct=score.delta_pct, window_days=score.window_days),
        "actions": _dedupe_actions(actions),
    }
    return _build_candidate(payload, magnitude=float(delta_pct))


def _station_candidate(score: FIStationTrustScore) -> _InsightCandidate | None:
    if score.level == score.level.TRUSTED:
        return None
    actions: list[dict] = []
    level = "HIGH"
    if score.level == score.level.WATCHLIST:
        actions.append(_action(ActionHintCode.MOVE_STATION_TO_WATCHLIST, severity="INFO"))
    if score.level == score.level.BLACKLIST:
        actions.append(_action(ActionHintCode.EXCLUDE_STATION_FROM_ROUTES, severity="REQUIRED"))
        actions.append(_action(ActionHintCode.REQUEST_COMPLIANCE_REVIEW, severity="INFO"))
        level = "VERY_HIGH"
    if not actions:
        return None
    payload = {
        "type": InsightType.STATION_TRUST.value,
        "entity_id": str(score.station_id),
        "level": level,
        "score": score.trust_score,
        "summary": explain.build_station_summary(level=score.level, reasons=_station_reasons(score)),
        "actions": _dedupe_actions(actions),
    }
    magnitude = float(100 - score.trust_score)
    return _build_candidate(payload, magnitude=magnitude)


def _build_candidate(payload: dict, *, magnitude: float) -> _InsightCandidate:
    actions = payload.get("actions", [])
    required_count = sum(1 for action in actions if action.get("severity") == "REQUIRED")
    level_rank = _LEVEL_RANK.get(str(payload.get("level", "")).upper(), 0)
    return _InsightCandidate(
        payload=payload,
        required_count=required_count,
        level_rank=level_rank,
        magnitude=magnitude,
        entity_id=str(payload.get("entity_id", "")),
    )


def _sort_key(candidate: _InsightCandidate) -> tuple:
    return (-candidate.required_count, -candidate.level_rank, -candidate.magnitude, candidate.entity_id)


def _action(code: ActionHintCode, *, severity: str) -> dict:
    return {
        "code": code.value,
        "title": _ACTION_TITLES[code],
        "severity": severity,
    }


def _dedupe_actions(actions: Iterable[dict]) -> list[dict]:
    seen = set()
    ordered: list[dict] = []
    for action in actions:
        code = action.get("code")
        if code in seen:
            continue
        seen.add(code)
        ordered.append(action)
    return ordered


def _driver_top_factors(score: FIDriverScore) -> list[dict]:
    explain_payload = score.explain or {}
    driver_payload = explain_payload.get("driver_behavior", {})
    top_factors = driver_payload.get("top_factors")
    return top_factors if isinstance(top_factors, list) else []


def _station_reasons(score: FIStationTrustScore) -> list[str]:
    explain_payload = score.explain or {}
    station_payload = explain_payload.get("station_trust", {})
    reasons = station_payload.get("reasons")
    return reasons if isinstance(reasons, list) else []


__all__ = ["build_fleet_insight_payload"]

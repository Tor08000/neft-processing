from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.fleet_intelligence import (
    DriverBehaviorLevel,
    FIDriverScore,
    FIStationTrustScore,
    FIVehicleEfficiencyScore,
    StationTrustLevel,
)
from app.services.fleet_intelligence import actionable
from app.services.fleet_intelligence.taxonomy import ActionHintCode, InsightType


def _driver_score(score: int) -> FIDriverScore:
    return FIDriverScore(
        tenant_id=1,
        client_id="client-1",
        driver_id=str(uuid4()),
        computed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        window_days=7,
        score=score,
        level=DriverBehaviorLevel.HIGH if score < 80 else DriverBehaviorLevel.VERY_HIGH,
        explain={"driver_behavior": {"top_factors": [{"factor": "night_fuel_tx_count", "value": 4.2}]}},
    )


def _vehicle_score(delta_pct: float) -> FIVehicleEfficiencyScore:
    return FIVehicleEfficiencyScore(
        tenant_id=1,
        client_id="client-1",
        vehicle_id=str(uuid4()),
        computed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        window_days=30,
        efficiency_score=80,
        baseline_ml_per_100km=300.0,
        actual_ml_per_100km=330.0,
        delta_pct=delta_pct,
        explain={"vehicle_efficiency": {"delta_pct": delta_pct}},
    )


def _station_score(level: StationTrustLevel) -> FIStationTrustScore:
    return FIStationTrustScore(
        tenant_id=1,
        station_id=str(uuid4()),
        network_id=str(uuid4()),
        computed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        window_days=7,
        trust_score=40,
        level=level,
        explain={"station_trust": {"reasons": ["Elevated decline rate"]}},
    )


def test_driver_thresholds_map_actions():
    payload = actionable.build_fleet_insight_payload(driver_scores=[_driver_score(72)])
    assert payload
    actions = payload["primary_insight"]["actions"]
    codes = {action["code"] for action in actions}
    assert ActionHintCode.REVIEW_DRIVER_BEHAVIOR.value in codes

    payload = actionable.build_fleet_insight_payload(driver_scores=[_driver_score(86)])
    actions = payload["primary_insight"]["actions"]
    codes = {action["code"] for action in actions}
    assert ActionHintCode.RESTRICT_NIGHT_FUELING.value in codes


def test_station_thresholds_map_actions():
    payload = actionable.build_fleet_insight_payload(station_scores=[_station_score(StationTrustLevel.TRUSTED)])
    assert payload is None

    payload = actionable.build_fleet_insight_payload(station_scores=[_station_score(StationTrustLevel.WATCHLIST)])
    actions = payload["primary_insight"]["actions"]
    codes = {action["code"] for action in actions}
    assert ActionHintCode.MOVE_STATION_TO_WATCHLIST.value in codes

    payload = actionable.build_fleet_insight_payload(station_scores=[_station_score(StationTrustLevel.BLACKLIST)])
    actions = payload["primary_insight"]["actions"]
    required = [action for action in actions if action["severity"] == "REQUIRED"]
    assert ActionHintCode.EXCLUDE_STATION_FROM_ROUTES.value in {action["code"] for action in required}


def test_vehicle_thresholds_map_actions():
    payload = actionable.build_fleet_insight_payload(vehicle_scores=[_vehicle_score(0.12)])
    actions = payload["primary_insight"]["actions"]
    assert actions[0]["severity"] == "INFO"

    payload = actionable.build_fleet_insight_payload(vehicle_scores=[_vehicle_score(0.30)])
    actions = payload["primary_insight"]["actions"]
    assert actions[0]["severity"] == "REQUIRED"


def test_primary_insight_prefers_required_then_level():
    driver = _driver_score(72)
    station = _station_score(StationTrustLevel.BLACKLIST)
    payload = actionable.build_fleet_insight_payload(driver_scores=[driver], station_scores=[station])
    assert payload
    assert payload["primary_insight"]["type"] == InsightType.STATION_TRUST.value

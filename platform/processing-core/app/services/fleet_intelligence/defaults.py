from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriverScoreWeights:
    off_route_fuel_count: int = 20
    night_fuel_tx_count: int = 10
    route_deviation_count: int = 15
    risk_block_count: int = 25
    review_required_count: int = 10
    tx_count: int = 5


@dataclass(frozen=True)
class DriverNormalizationThresholds:
    off_route_fuel_count: int = 2
    night_fuel_tx_count: int = 5
    route_deviation_count: int = 2
    risk_block_count: int = 1
    review_required_count: int = 3
    tx_count: int = 20


DRIVER_SCORE_WEIGHTS = DriverScoreWeights()
DRIVER_SCORE_THRESHOLDS = DriverNormalizationThresholds()

STATION_RISK_BLOCK_RATE_HIGH = 0.05
STATION_DECLINE_RATE_HIGH = 0.1
STATION_BURST_EVENTS_HIGH = 1
STATION_VOLUME_DEVIATION_HIGH = 0.2

VEHICLE_BASELINE_DAYS = 30

__all__ = [
    "DRIVER_SCORE_WEIGHTS",
    "DRIVER_SCORE_THRESHOLDS",
    "STATION_RISK_BLOCK_RATE_HIGH",
    "STATION_DECLINE_RATE_HIGH",
    "STATION_BURST_EVENTS_HIGH",
    "STATION_VOLUME_DEVIATION_HIGH",
    "VEHICLE_BASELINE_DAYS",
]

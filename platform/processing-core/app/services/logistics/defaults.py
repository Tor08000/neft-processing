from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteConstraintDefaults:
    max_route_deviation_m: int = 3000
    max_stop_radius_m: int = 700
    allowed_fuel_window_minutes: int = 120


@dataclass(frozen=True)
class UnexpectedStopDefaults:
    stop_speed_threshold_kmh: float = 3.0
    unexpected_stop_min_duration_minutes: int = 20
    unexpected_stop_grace_minutes: int = 10


@dataclass(frozen=True)
class OffRouteDefaults:
    off_route_min_duration_minutes: int = 15
    off_route_consecutive_points: int = 3


@dataclass(frozen=True)
class StopOutOfRadiusDefaults:
    stop_out_of_radius_m: int = 700
    stop_out_of_radius_high_m: int = 1500


@dataclass(frozen=True)
class FuelLinkDefaults:
    max_stop_radius_m: int = 700
    max_stop_radius_high_m: int = 1500
    allowed_fuel_window_minutes: int = 120


@dataclass(frozen=True)
class ETAAccuracyDefaults:
    eta_error_medium_minutes: int = 30
    eta_error_high_minutes: int = 60


@dataclass(frozen=True)
class RiskSignalDefaults:
    off_route_severity: int = 60
    off_route_severity_30m: int = 80
    off_route_severity_60m: int = 90
    fuel_off_route_severity: int = 85
    fuel_stop_mismatch_severity: int = 70
    stop_out_of_radius_high_severity: int = 80
    unexpected_stop_40m_severity: int = 70
    unexpected_stop_90m_severity: int = 85
    velocity_anomaly_severity: int = 75
    eta_anomaly_severity: int = 70
    eta_anomaly_medium_severity: int = 60


@dataclass(frozen=True)
class VelocityDefaults:
    teleport_speed_kmh: float = 150.0
    teleport_min_distance_m: int = 5000


@dataclass(frozen=True)
class HealthDefaults:
    tracking_stale_minutes: int = 30


ROUTE_CONSTRAINT_DEFAULTS = RouteConstraintDefaults()
UNEXPECTED_STOP_DEFAULTS = UnexpectedStopDefaults()
OFF_ROUTE_DEFAULTS = OffRouteDefaults()
STOP_RADIUS_DEFAULTS = StopOutOfRadiusDefaults()
FUEL_LINK_DEFAULTS = FuelLinkDefaults()
ETA_ACCURACY_DEFAULTS = ETAAccuracyDefaults()
RISK_SIGNAL_DEFAULTS = RiskSignalDefaults()
VELOCITY_DEFAULTS = VelocityDefaults()
HEALTH_DEFAULTS = HealthDefaults()

__all__ = [
    "ROUTE_CONSTRAINT_DEFAULTS",
    "UNEXPECTED_STOP_DEFAULTS",
    "OFF_ROUTE_DEFAULTS",
    "STOP_RADIUS_DEFAULTS",
    "FUEL_LINK_DEFAULTS",
    "ETA_ACCURACY_DEFAULTS",
    "RISK_SIGNAL_DEFAULTS",
    "VELOCITY_DEFAULTS",
    "HEALTH_DEFAULTS",
]

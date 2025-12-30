from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    Explain,
)


class MockProvider(BaseProvider):
    name = "mock"

    def compute_eta(self, request: EtaRequest) -> EtaResponse:
        distance_km = _route_distance_km(request)
        speed_kmh = _estimated_speed(request)
        eta_minutes = max(1, int(round(distance_km / max(speed_kmh, 1) * 60)))
        confidence = _eta_confidence(request)
        explain = self.explain_eta(request)
        return EtaResponse(
            eta_minutes=eta_minutes,
            confidence=confidence,
            provider=self.name,
            explain=explain,
        )

    def compute_deviation(self, request: DeviationRequest) -> DeviationResponse:
        deviation_m = _distance_to_polyline_m(request)
        is_violation = deviation_m > request.threshold_meters
        confidence = 0.9 if is_violation else 0.78
        explain = self.explain_deviation(request)
        return DeviationResponse(
            deviation_meters=int(round(deviation_m)),
            is_violation=is_violation,
            confidence=confidence,
            explain=explain,
        )

    def explain_eta(self, request: EtaRequest) -> Explain:
        traffic = (request.context.traffic if request.context else None) or "normal"
        primary_reason = {
            "normal": "NORMAL_TRAFFIC",
            "slow": "SLOW_TRAFFIC",
            "heavy": "HEAVY_TRAFFIC",
            "light": "LIGHT_TRAFFIC",
        }.get(traffic, "NORMAL_TRAFFIC")
        return Explain(
            primary_reason=primary_reason,
            secondary=[],
            confidence=_eta_confidence(request),
            factors=["ROUTE_LENGTH", "AVERAGE_SPEED"],
        )

    def explain_deviation(self, request: DeviationRequest) -> Explain:
        deviation_m = _distance_to_polyline_m(request)
        is_violation = deviation_m > request.threshold_meters
        secondary = ["OUT_OF_POLYLINE"] if is_violation else ["WITHIN_THRESHOLD"]
        return Explain(
            primary_reason="ROUTE_DEVIATION" if is_violation else "ROUTE_ON_PATH",
            secondary=secondary,
            confidence=0.9 if is_violation else 0.78,
            factors=["DISTANCE_FROM_PATH"],
        )


def _estimated_speed(request: EtaRequest) -> float:
    vehicle_type = (request.vehicle.type or "truck").lower()
    base_speed = {
        "truck": 60.0,
        "van": 70.0,
        "car": 80.0,
    }.get(vehicle_type, 55.0)
    traffic = (request.context.traffic if request.context else None) or "normal"
    traffic_factor = {
        "normal": 1.0,
        "slow": 0.7,
        "heavy": 0.5,
        "light": 1.1,
    }.get(traffic, 1.0)
    weather = (request.context.weather if request.context else None) or "clear"
    weather_factor = {
        "clear": 1.0,
        "rain": 0.85,
        "snow": 0.7,
    }.get(weather, 1.0)
    return base_speed * traffic_factor * weather_factor


def _eta_confidence(request: EtaRequest) -> float:
    traffic = (request.context.traffic if request.context else None) or "normal"
    base = {
        "normal": 0.82,
        "light": 0.86,
        "slow": 0.72,
        "heavy": 0.64,
    }.get(traffic, 0.8)
    point_bonus = min(len(request.points), 6) * 0.01
    return min(0.95, round(base + point_bonus, 2))


def _route_distance_km(request: EtaRequest) -> float:
    points = request.points
    if len(points) < 2:
        return 0.1
    total = 0.0
    for start, end in zip(points, points[1:]):
        total += _haversine_km(start.lat, start.lon, end.lat, end.lon)
    return round(total, 3)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return 2 * radius * asin(sqrt(a))


def _distance_to_polyline_m(request: DeviationRequest) -> float:
    point = request.actual_point
    if len(request.planned_polyline) < 2:
        return 0.0
    min_distance = None
    for start, end in zip(request.planned_polyline, request.planned_polyline[1:]):
        distance = _point_to_segment_distance_m(point.lat, point.lon, start, end)
        min_distance = distance if min_distance is None else min(min_distance, distance)
    return float(min_distance or 0.0)


def _point_to_segment_distance_m(
    lat: float,
    lon: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    lat1, lon1 = start
    lat2, lon2 = end
    if lat1 == lat2 and lon1 == lon2:
        return _haversine_m(lat, lon, lat1, lon1)
    dx = lon2 - lon1
    dy = lat2 - lat1
    if dx == 0 and dy == 0:
        return _haversine_m(lat, lon, lat1, lon1)
    t = ((lon - lon1) * dx + (lat - lat1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_lon = lon1 + t * dx
    proj_lat = lat1 + t * dy
    return _haversine_m(lat, lon, proj_lat, proj_lon)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return 2 * radius * asin(sqrt(a))


__all__ = ["MockProvider"]

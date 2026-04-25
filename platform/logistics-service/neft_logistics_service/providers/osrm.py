from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    Explain,
    RoutePreviewGeometryPoint,
    RoutePreviewRequest,
    RoutePreviewResponse,
)
from neft_logistics_service.settings import get_settings

settings = get_settings()


@dataclass
class OSRMProvider(BaseProvider):
    base_url: str = settings.osrm_base_url
    timeout_seconds: int = settings.osrm_timeout_seconds

    name = "osrm"

    def preview_route(self, request: RoutePreviewRequest) -> RoutePreviewResponse:
        preview = self._fetch_route_preview([(point.lat, point.lon) for point in request.points])
        return RoutePreviewResponse(
            provider=self.name,
            geometry=[RoutePreviewGeometryPoint(lat=lat, lon=lon) for lat, lon in preview["geometry"]],
            distance_km=preview["distance_km"],
            eta_minutes=max(1, int(round(preview["duration_seconds"] / 60))),
            confidence=0.82,
            computed_at=datetime.now(timezone.utc),
            degraded=False,
            degradation_reason=None,
        )

    def compute_eta(self, request: EtaRequest) -> EtaResponse:
        duration_seconds = self._fetch_route_duration(request.points)
        eta_minutes = max(1, int(round(duration_seconds / 60)))
        explain = self.explain_eta(request)
        return EtaResponse(
            eta_minutes=eta_minutes,
            confidence=0.82,
            provider=self.name,
            explain=explain,
        )

    def compute_deviation(self, request: DeviationRequest) -> DeviationResponse:
        geometry = self._fetch_route_geometry(request.planned_polyline)
        deviation_m = _distance_to_polyline_m(request.actual_point.lat, request.actual_point.lon, geometry)
        is_violation = deviation_m > request.threshold_meters
        return DeviationResponse(
            deviation_meters=int(round(deviation_m)),
            is_violation=is_violation,
            confidence=0.85 if is_violation else 0.78,
            provider=self.name,
            explain=self.explain_deviation(request),
        )

    def explain_eta(self, request: EtaRequest) -> Explain:
        return Explain(
            primary_reason="OSRM_ROUTE",
            secondary=[],
            confidence=0.82,
            factors=["ROUTE_DURATION"],
        )

    def explain_deviation(self, request: DeviationRequest) -> Explain:
        return Explain(
            primary_reason="OSRM_GEOMETRY",
            secondary=[],
            confidence=0.82,
            factors=["ROUTE_GEOMETRY"],
        )

    def _fetch_route_duration(self, points: Iterable) -> float:
        coordinates = _encode_coordinates(points)
        query = urlencode({"overview": "false"})
        url = f"{self.base_url}/route/v1/driving/{coordinates}?{query}"
        payload = _get_json(url, timeout=self.timeout_seconds)
        return float(payload["routes"][0]["duration"])

    def _fetch_route_preview(self, points: Iterable[tuple[float, float]]) -> dict[str, float | list[tuple[float, float]]]:
        coordinates = _encode_latlon(points)
        query = urlencode({"overview": "full", "geometries": "polyline"})
        url = f"{self.base_url}/route/v1/driving/{coordinates}?{query}"
        payload = _get_json(url, timeout=self.timeout_seconds)
        route = payload["routes"][0]
        return {
            "geometry": decode_polyline(route["geometry"]),
            "distance_km": round(float(route["distance"]) / 1000, 3),
            "duration_seconds": float(route["duration"]),
        }

    def _fetch_route_geometry(self, polyline: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
        coordinates = _encode_latlon(polyline)
        query = urlencode({"overview": "full", "geometries": "polyline"})
        url = f"{self.base_url}/route/v1/driving/{coordinates}?{query}"
        payload = _get_json(url, timeout=self.timeout_seconds)
        geometry = payload["routes"][0]["geometry"]
        return decode_polyline(geometry)


def _get_json(url: str, timeout: int) -> dict:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"osrm_http_error:{exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("osrm_unavailable") from exc


def _encode_coordinates(points: Iterable) -> str:
    return ";".join(f"{point.lon},{point.lat}" for point in points)


def _encode_latlon(points: Iterable[tuple[float, float]]) -> str:
    return ";".join(f"{lon},{lat}" for lat, lon in points)


def decode_polyline(polyline: str) -> list[tuple[float, float]]:
    index = 0
    lat = 0
    lon = 0
    coordinates: list[tuple[float, float]] = []
    while index < len(polyline):
        lat_change, index = _decode_value(polyline, index)
        lon_change, index = _decode_value(polyline, index)
        lat += lat_change
        lon += lon_change
        coordinates.append((lat / 1e5, lon / 1e5))
    return coordinates


def _decode_value(polyline: str, index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        value = ord(polyline[index]) - 63
        index += 1
        result |= (value & 0x1F) << shift
        shift += 5
        if value < 0x20:
            break
    delta = ~(result >> 1) if result & 1 else result >> 1
    return delta, index


def _distance_to_polyline_m(lat: float, lon: float, polyline: list[tuple[float, float]]) -> float:
    if len(polyline) < 2:
        return 0.0
    min_distance = None
    for start, end in zip(polyline, polyline[1:]):
        distance = _point_to_segment_distance_m(lat, lon, start, end)
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


__all__ = ["OSRMProvider", "decode_polyline"]

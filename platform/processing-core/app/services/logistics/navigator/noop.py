from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from app.services.logistics.navigator.base import DeviationScore, ETAResult, GeoPoint, RouteSnapshot


_AVG_SPEED_KMH = 48.0


@dataclass(frozen=True)
class NoopNavigator:
    provider: str = "noop"

    def build_route(self, stops: list[GeoPoint]) -> RouteSnapshot:
        distance_km = 0.0
        if len(stops) >= 2:
            for start, end in zip(stops, stops[1:]):
                distance_km += self.distance(start, end)
        return RouteSnapshot(provider=self.provider, geometry=stops, distance_km=distance_km)

    def estimate_eta(self, route: RouteSnapshot) -> ETAResult:
        eta_minutes = int(round((route.distance_km / _AVG_SPEED_KMH) * 60)) if route.distance_km else 0
        return ETAResult(
            eta_minutes=eta_minutes,
            assumptions=["no traffic", f"avg_speed={int(_AVG_SPEED_KMH)}kmh"],
            method="straight_line",
        )

    def distance(self, a: GeoPoint, b: GeoPoint) -> float:
        radius_km = 6371.0
        phi1 = radians(a.lat)
        phi2 = radians(b.lat)
        dphi = radians(b.lat - a.lat)
        dlambda = radians(b.lon - a.lon)

        value = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
        return 2 * radius_km * asin(sqrt(value))

    def deviation_score(self, route: RouteSnapshot, actual_points: list[GeoPoint]) -> DeviationScore:
        expected_distance = route.distance_km
        actual_distance = 0.0
        if len(actual_points) >= 2:
            for start, end in zip(actual_points, actual_points[1:]):
                actual_distance += self.distance(start, end)
        delta_pct = 0.0
        if expected_distance > 0:
            delta_pct = max(0.0, (actual_distance - expected_distance) / expected_distance * 100)
        score = min(1.0, delta_pct * 0.0175)
        reason = "significant off-route movement" if score >= 0.5 else "minor deviation"
        return DeviationScore(
            expected_distance_km=round(expected_distance, 3),
            actual_distance_km=round(actual_distance, 3),
            delta_pct=round(delta_pct, 2),
            score=round(score, 2),
            reason=reason,
        )

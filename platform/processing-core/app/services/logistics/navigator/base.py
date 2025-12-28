from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteSnapshot:
    provider: str
    geometry: list[GeoPoint]
    distance_km: float


@dataclass(frozen=True)
class ETAResult:
    eta_minutes: int
    assumptions: list[str]
    method: str


@dataclass(frozen=True)
class DeviationScore:
    expected_distance_km: float
    actual_distance_km: float
    delta_pct: float
    score: float
    reason: str


class NavigatorAdapter(Protocol):
    provider: str

    def build_route(self, stops: list[GeoPoint]) -> RouteSnapshot:
        ...

    def estimate_eta(self, route: RouteSnapshot) -> ETAResult:
        ...

    def distance(self, a: GeoPoint, b: GeoPoint) -> float:
        ...

    def deviation_score(self, route: RouteSnapshot, actual_points: list[GeoPoint]) -> DeviationScore:
        ...

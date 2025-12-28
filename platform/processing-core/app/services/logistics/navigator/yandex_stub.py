from __future__ import annotations

from dataclasses import dataclass

from app.services.logistics.navigator.base import DeviationScore, ETAResult, GeoPoint, RouteSnapshot
from app.services.logistics.navigator.noop import NoopNavigator


@dataclass(frozen=True)
class YandexStubNavigator:
    provider: str = "yandex"

    def build_route(self, stops: list[GeoPoint]) -> RouteSnapshot:
        base = NoopNavigator(provider=self.provider)
        return base.build_route(stops)

    def estimate_eta(self, route: RouteSnapshot) -> ETAResult:
        base = NoopNavigator(provider=self.provider)
        eta = base.estimate_eta(route)
        return ETAResult(
            eta_minutes=eta.eta_minutes,
            assumptions=["stub_provider=yandex", *eta.assumptions],
            method="stub_straight_line",
        )

    def distance(self, a: GeoPoint, b: GeoPoint) -> float:
        base = NoopNavigator(provider=self.provider)
        return base.distance(a, b)

    def deviation_score(self, route: RouteSnapshot, actual_points: list[GeoPoint]) -> DeviationScore:
        base = NoopNavigator(provider=self.provider)
        return base.deviation_score(route, actual_points)

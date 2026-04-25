from __future__ import annotations

from dataclasses import dataclass, field

from app.services.metrics_helpers import Histogram


REPORTS_ROUTE_DURATION_BUCKETS = [0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]


@dataclass
class ReportsRouteMetrics:
    requests_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    duration_seconds: dict[tuple[str, str], Histogram] = field(default_factory=dict)

    def mark_request(self, route: str, method: str, outcome: str, *, duration_seconds: float) -> None:
        request_key = (route, method, outcome)
        self.requests_total[request_key] = self.requests_total.get(request_key, 0) + 1

        duration_key = (route, method)
        histogram = self.duration_seconds.get(duration_key)
        if histogram is None:
            histogram = Histogram(buckets=REPORTS_ROUTE_DURATION_BUCKETS)
            self.duration_seconds[duration_key] = histogram
        histogram.observe(max(0.0, duration_seconds))

    def reset(self) -> None:
        self.requests_total.clear()
        self.duration_seconds.clear()


metrics = ReportsRouteMetrics()


__all__ = ["ReportsRouteMetrics", "metrics"]

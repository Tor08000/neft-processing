from __future__ import annotations

from dataclasses import dataclass, field

from app.services.metrics_helpers import Histogram


SCHEDULE_LAG_BUCKETS = [60, 120, 300, 600, 900, 1800, 3600]


@dataclass
class ReportScheduleMetrics:
    triggered_total: dict[tuple[str, str], int] = field(default_factory=dict)
    skipped_total: dict[str, int] = field(default_factory=dict)
    trigger_lag_seconds: Histogram = field(default_factory=lambda: Histogram(buckets=SCHEDULE_LAG_BUCKETS))

    def mark_triggered(self, report_type: str, export_format: str) -> None:
        key = (report_type, export_format)
        self.triggered_total[key] = self.triggered_total.get(key, 0) + 1

    def mark_skipped(self, reason: str) -> None:
        self.skipped_total[reason] = self.skipped_total.get(reason, 0) + 1

    def observe_lag(self, seconds: float) -> None:
        self.trigger_lag_seconds.observe(max(0.0, seconds))

    def reset(self) -> None:
        self.triggered_total.clear()
        self.skipped_total.clear()
        self.trigger_lag_seconds.reset()


metrics = ReportScheduleMetrics()


__all__ = ["ReportScheduleMetrics", "metrics"]

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.metrics_helpers import Histogram


EXPORT_DURATION_BUCKETS = [1, 5, 10, 30, 60, 120, 300, 600, 900, 1800]
EXPORT_ROWS_BUCKETS = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]


@dataclass
class ExportJobMetrics:
    created_total: dict[tuple[str, str], int] = field(default_factory=dict)
    completed_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    duration_seconds: dict[tuple[str, str], Histogram] = field(default_factory=dict)
    rows: dict[tuple[str, str], Histogram] = field(default_factory=dict)
    failures_total: dict[str, int] = field(default_factory=dict)

    def mark_created(self, report_type: str, export_format: str) -> None:
        key = (report_type, export_format)
        self.created_total[key] = self.created_total.get(key, 0) + 1

    def mark_completed(
        self,
        report_type: str,
        export_format: str,
        status: str,
        *,
        duration_seconds: float | None = None,
        row_count: int | None = None,
    ) -> None:
        key = (report_type, export_format, status)
        self.completed_total[key] = self.completed_total.get(key, 0) + 1
        histogram_key = (report_type, export_format)
        if duration_seconds is not None:
            histogram = self.duration_seconds.get(histogram_key)
            if histogram is None:
                histogram = Histogram(buckets=EXPORT_DURATION_BUCKETS)
                self.duration_seconds[histogram_key] = histogram
            histogram.observe(duration_seconds)
        if row_count is not None:
            rows_histogram = self.rows.get(histogram_key)
            if rows_histogram is None:
                rows_histogram = Histogram(buckets=EXPORT_ROWS_BUCKETS)
                self.rows[histogram_key] = rows_histogram
            rows_histogram.observe(float(row_count))

    def mark_failure(self, reason: str) -> None:
        self.failures_total[reason] = self.failures_total.get(reason, 0) + 1

    def reset(self) -> None:
        self.created_total.clear()
        self.completed_total.clear()
        self.duration_seconds.clear()
        self.rows.clear()
        self.failures_total.clear()


metrics = ExportJobMetrics()


__all__ = ["ExportJobMetrics", "metrics"]

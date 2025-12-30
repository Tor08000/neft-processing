from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BiMetrics:
    ingest_events_total: dict[str, int] = field(default_factory=dict)
    ingest_lag_seconds: float = 0.0
    aggregate_total: dict[str, int] = field(default_factory=dict)
    exports_generated_total: int = 0
    exports_failed_total: int = 0

    def mark_ingest(self, status: str) -> None:
        self.ingest_events_total[status] = self.ingest_events_total.get(status, 0) + 1

    def mark_aggregate(self, status: str) -> None:
        self.aggregate_total[status] = self.aggregate_total.get(status, 0) + 1

    def mark_export_generated(self) -> None:
        self.exports_generated_total += 1

    def mark_export_failed(self) -> None:
        self.exports_failed_total += 1


metrics = BiMetrics()


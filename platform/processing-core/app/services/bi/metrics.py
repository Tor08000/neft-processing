from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BiMetrics:
    ingest_events_total: dict[str, int] = field(default_factory=dict)
    ingest_lag_seconds: float = 0.0
    aggregate_total: dict[str, int] = field(default_factory=dict)
    exports_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    export_generate_duration_seconds: float = 0.0
    clickhouse_sync_total: dict[tuple[str, str], int] = field(default_factory=dict)
    clickhouse_lag_seconds: dict[str, float] = field(default_factory=dict)

    def mark_ingest(self, status: str) -> None:
        self.ingest_events_total[status] = self.ingest_events_total.get(status, 0) + 1

    def mark_aggregate(self, status: str) -> None:
        self.aggregate_total[status] = self.aggregate_total.get(status, 0) + 1

    def mark_export_generated(self, dataset: str, export_format: str, status: str, duration_seconds: float) -> None:
        key = (dataset, export_format, status)
        self.exports_total[key] = self.exports_total.get(key, 0) + 1
        self.export_generate_duration_seconds = duration_seconds

    def mark_export_failed(self, dataset: str, export_format: str, status: str) -> None:
        key = (dataset, export_format, status)
        self.exports_total[key] = self.exports_total.get(key, 0) + 1

    def mark_clickhouse_sync(self, dataset: str, status: str) -> None:
        key = (dataset, status)
        self.clickhouse_sync_total[key] = self.clickhouse_sync_total.get(key, 0) + 1

    def mark_clickhouse_lag(self, dataset: str, lag_seconds: float) -> None:
        self.clickhouse_lag_seconds[dataset] = lag_seconds


metrics = BiMetrics()

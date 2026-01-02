from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FleetMetrics:
    ingest_jobs_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    ingest_items_total: Dict[str, int] = field(default_factory=dict)
    limit_breaches_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    transactions_total: int = 0
    export_requests_total: int = 0

    def mark_ingest_job(self, status: str, provider: str) -> None:
        key = (status, provider)
        self.ingest_jobs_total[key] = self.ingest_jobs_total.get(key, 0) + 1

    def mark_ingest_item(self, result: str, count: int = 1) -> None:
        self.ingest_items_total[result] = self.ingest_items_total.get(result, 0) + count

    def mark_limit_breach(self, breach_type: str, scope: str) -> None:
        key = (breach_type, scope)
        self.limit_breaches_total[key] = self.limit_breaches_total.get(key, 0) + 1

    def mark_transaction(self, count: int = 1) -> None:
        self.transactions_total += count

    def mark_export_request(self, count: int = 1) -> None:
        self.export_requests_total += count

    def reset(self) -> None:
        self.ingest_jobs_total.clear()
        self.ingest_items_total.clear()
        self.limit_breaches_total.clear()
        self.transactions_total = 0
        self.export_requests_total = 0


metrics = FleetMetrics()

__all__ = ["FleetMetrics", "metrics"]

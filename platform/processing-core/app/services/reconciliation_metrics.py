from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ReconciliationMetrics:
    runs_total: dict[str, int] = field(default_factory=dict)
    discrepancies_total: dict[str, int] = field(default_factory=dict)
    resolved_total: int = 0
    total_delta_abs: Decimal = Decimal("0")

    def mark_run(self, *, scope: str, status: str, count: int = 1) -> None:
        key = f"{scope}:{status}"
        self.runs_total[key] = self.runs_total.get(key, 0) + count

    def mark_discrepancy(self, discrepancy_type: str, status: str, count: int = 1) -> None:
        key = f"{discrepancy_type}:{status}"
        self.discrepancies_total[key] = self.discrepancies_total.get(key, 0) + count

    def mark_resolved(self, count: int = 1) -> None:
        self.resolved_total += count

    def observe_delta_abs(self, delta: Decimal) -> None:
        self.total_delta_abs += abs(delta)

    def reset(self) -> None:
        self.runs_total.clear()
        self.discrepancies_total.clear()
        self.resolved_total = 0
        self.total_delta_abs = Decimal("0")


metrics = ReconciliationMetrics()


__all__ = ["ReconciliationMetrics", "metrics"]

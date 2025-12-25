from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AccountingExportMetrics:
    overdue_batches_total: int = 0
    unconfirmed_batches_total: int = 0

    def mark_overdue(self, count: int = 1) -> None:
        self.overdue_batches_total += count

    def mark_unconfirmed(self, count: int = 1) -> None:
        self.unconfirmed_batches_total += count

    def reset(self) -> None:
        self.overdue_batches_total = 0
        self.unconfirmed_batches_total = 0


metrics = AccountingExportMetrics()


__all__ = ["AccountingExportMetrics", "metrics"]

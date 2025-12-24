from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PayoutMetrics:
    batches_created_total: int = 0
    batches_errors_total: int = 0
    batches_settled_total: int = 0
    reconcile_mismatch_total: int = 0
    payout_amount_total: Decimal = Decimal("0")

    def mark_created(self, amount: Decimal) -> None:
        self.batches_created_total += 1
        self.payout_amount_total += amount

    def mark_error(self) -> None:
        self.batches_errors_total += 1

    def mark_settled(self) -> None:
        self.batches_settled_total += 1

    def mark_reconcile_mismatch(self) -> None:
        self.reconcile_mismatch_total += 1

    def reset(self) -> None:
        self.batches_created_total = 0
        self.batches_errors_total = 0
        self.batches_settled_total = 0
        self.reconcile_mismatch_total = 0
        self.payout_amount_total = Decimal("0")


metrics = PayoutMetrics()

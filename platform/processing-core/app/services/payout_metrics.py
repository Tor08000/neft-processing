from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PayoutMetrics:
    batches_created_total: int = 0
    batches_errors_total: int = 0
    batches_settled_total: int = 0
    reconcile_mismatch_total: int = 0
    payout_amount_total: Decimal = Decimal("0")
    exports_total: dict[tuple[str, str], int] = field(default_factory=dict)
    export_errors_total: int = 0
    export_bytes_total: dict[str, int] = field(default_factory=dict)
    export_download_total: dict[str, int] = field(default_factory=dict)
    export_download_errors_total: int = 0

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
        self.exports_total = {}
        self.export_errors_total = 0
        self.export_bytes_total = {}
        self.export_download_total = {}
        self.export_download_errors_total = 0

    def mark_export(self, export_format: str, state: str) -> None:
        key = (export_format, state)
        self.exports_total[key] = self.exports_total.get(key, 0) + 1

    def mark_export_error(self) -> None:
        self.export_errors_total += 1

    def mark_export_bytes(self, export_format: str, size_bytes: int) -> None:
        self.export_bytes_total[export_format] = self.export_bytes_total.get(export_format, 0) + size_bytes

    def mark_export_download(self, export_format: str) -> None:
        self.export_download_total[export_format] = self.export_download_total.get(export_format, 0) + 1

    def mark_export_download_error(self) -> None:
        self.export_download_errors_total += 1


metrics = PayoutMetrics()

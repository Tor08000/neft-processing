from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PartnerTrustMetrics:
    settlement_breakdown_requests_total: int = 0
    exports_generated_total: int = 0

    def mark_settlement_breakdown_requested(self) -> None:
        self.settlement_breakdown_requests_total += 1

    def mark_export_generated(self) -> None:
        self.exports_generated_total += 1

    def reset(self) -> None:
        self.settlement_breakdown_requests_total = 0
        self.exports_generated_total = 0


metrics = PartnerTrustMetrics()


__all__ = ["PartnerTrustMetrics", "metrics"]

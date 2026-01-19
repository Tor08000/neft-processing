from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PartnerTrustMetrics:
    settlement_breakdown_requests_total: int = 0
    ledger_explain_requests_total: int = 0
    payout_trace_requests_total: int = 0
    exports_created_total: int = 0

    def mark_settlement_breakdown_requested(self) -> None:
        self.settlement_breakdown_requests_total += 1

    def mark_ledger_explain_requested(self) -> None:
        self.ledger_explain_requests_total += 1

    def mark_payout_trace_requested(self) -> None:
        self.payout_trace_requests_total += 1

    def mark_export_created(self) -> None:
        self.exports_created_total += 1

    def reset(self) -> None:
        self.settlement_breakdown_requests_total = 0
        self.ledger_explain_requests_total = 0
        self.payout_trace_requests_total = 0
        self.exports_created_total = 0


metrics = PartnerTrustMetrics()


__all__ = ["PartnerTrustMetrics", "metrics"]

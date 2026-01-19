from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MorRuntimeMetrics:
    settlement_immutable_violation_total: int = 0
    payout_blocked_total: dict[str, int] = field(default_factory=dict)
    clawback_required_total: int = 0
    admin_override_total: int = 0

    def mark_settlement_immutable_violation(self) -> None:
        self.settlement_immutable_violation_total += 1

    def mark_payout_blocked(self, reason: str) -> None:
        self.payout_blocked_total[reason] = self.payout_blocked_total.get(reason, 0) + 1

    def mark_clawback_required(self) -> None:
        self.clawback_required_total += 1

    def mark_admin_override(self) -> None:
        self.admin_override_total += 1

    def reset(self) -> None:
        self.settlement_immutable_violation_total = 0
        self.payout_blocked_total = {}
        self.clawback_required_total = 0
        self.admin_override_total = 0


metrics = MorRuntimeMetrics()


__all__ = ["MorRuntimeMetrics", "metrics"]

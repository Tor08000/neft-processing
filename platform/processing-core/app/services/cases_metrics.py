from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CasesMetrics:
    escalations_total: Dict[int, int] = field(default_factory=dict)
    sla_breaches_total: Dict[str, int] = field(default_factory=dict)

    def mark_escalation(self, level: int) -> None:
        self.escalations_total[level] = self.escalations_total.get(level, 0) + 1

    def mark_sla_breach(self, kind: str) -> None:
        self.sla_breaches_total[kind] = self.sla_breaches_total.get(kind, 0) + 1

    def reset(self) -> None:
        self.escalations_total.clear()
        self.sla_breaches_total.clear()


metrics = CasesMetrics()


__all__ = ["CasesMetrics", "metrics"]

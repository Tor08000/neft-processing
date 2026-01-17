from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CasesMetrics:
    escalations_total: Dict[int, int] = field(default_factory=dict)
    sla_breaches_total: Dict[str, int] = field(default_factory=dict)
    support_tickets_created_total: Dict[str, int] = field(default_factory=dict)
    support_tickets_closed_total: int = 0

    def mark_escalation(self, level: int) -> None:
        self.escalations_total[level] = self.escalations_total.get(level, 0) + 1

    def mark_sla_breach(self, kind: str) -> None:
        self.sla_breaches_total[kind] = self.sla_breaches_total.get(kind, 0) + 1

    def mark_support_ticket_created(self, priority: str) -> None:
        self.support_tickets_created_total[priority] = self.support_tickets_created_total.get(priority, 0) + 1

    def mark_support_ticket_closed(self) -> None:
        self.support_tickets_closed_total += 1

    def reset(self) -> None:
        self.escalations_total.clear()
        self.sla_breaches_total.clear()
        self.support_tickets_created_total.clear()
        self.support_tickets_closed_total = 0


metrics = CasesMetrics()


__all__ = ["CasesMetrics", "metrics"]

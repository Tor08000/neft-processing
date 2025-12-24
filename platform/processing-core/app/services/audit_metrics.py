from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuditMetrics:
    events_total: dict[str, int] = field(default_factory=dict)
    write_errors_total: int = 0
    verify_broken_total: int = 0

    def mark_event(self, event_type: str) -> None:
        self.events_total[event_type] = self.events_total.get(event_type, 0) + 1

    def mark_write_error(self) -> None:
        self.write_errors_total += 1

    def mark_verify_broken(self) -> None:
        self.verify_broken_total += 1

    def reset(self) -> None:
        self.events_total.clear()
        self.write_errors_total = 0
        self.verify_broken_total = 0


metrics = AuditMetrics()


__all__ = ["metrics", "AuditMetrics"]

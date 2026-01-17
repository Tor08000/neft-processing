from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NotificationMetrics:
    created_total: dict[tuple[str, str], int] = field(default_factory=dict)

    def mark_created(self, event_type: str, severity: str) -> None:
        key = (event_type, severity)
        self.created_total[key] = self.created_total.get(key, 0) + 1

    def reset(self) -> None:
        self.created_total.clear()


metrics = NotificationMetrics()


__all__ = ["NotificationMetrics", "metrics"]

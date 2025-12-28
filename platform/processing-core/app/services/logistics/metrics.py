from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LogisticsMetrics:
    counters: dict[str, int] = field(default_factory=dict)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)


metrics = LogisticsMetrics()

__all__ = ["LogisticsMetrics", "metrics"]

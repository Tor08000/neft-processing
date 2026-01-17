from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Histogram:
    buckets: list[float]
    counts: dict[float, int] = field(default_factory=dict)
    total_count: int = 0
    total_sum: float = 0.0

    def observe(self, value: float) -> None:
        self.total_count += 1
        self.total_sum += float(value)
        for bucket in self.buckets:
            if value <= bucket:
                self.counts[bucket] = self.counts.get(bucket, 0) + 1

    def reset(self) -> None:
        self.counts.clear()
        self.total_count = 0
        self.total_sum = 0.0


__all__ = ["Histogram"]

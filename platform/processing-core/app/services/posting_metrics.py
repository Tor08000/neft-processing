from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict

from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class PostingMetrics:
    """In-memory metrics collector for posting pipeline."""

    successful_postings: int = 0
    failed_postings: int = 0
    contractual_declines: int = 0
    status_distribution: Counter = field(default_factory=Counter)
    latencies_ms: list[float] = field(default_factory=list)

    def observe_posting(self, success: bool, latency_ms: float) -> None:
        if success:
            self.successful_postings += 1
        else:
            self.failed_postings += 1
        self.latencies_ms.append(latency_ms)

    def inc_contractual_decline(self) -> None:
        self.contractual_declines += 1

    def mark_status(self, status: str) -> None:
        self.status_distribution[status] += 1

    def snapshot(self) -> Dict[str, object]:  # pragma: no cover - debugging helper
        return {
            "successful_postings": self.successful_postings,
            "failed_postings": self.failed_postings,
            "contractual_declines": self.contractual_declines,
            "status_distribution": dict(self.status_distribution),
            "latency_p99_ms": self._percentile(99),
        }

    def _percentile(self, pct: float) -> float | None:
        if not self.latencies_ms:
            return None
        sorted_values = sorted(self.latencies_ms)
        k = (len(sorted_values) - 1) * (pct / 100)
        f = int(k)
        c = min(f + 1, len(sorted_values) - 1)
        if f == c:
            return sorted_values[int(k)]
        d0 = sorted_values[f] * (c - k)
        d1 = sorted_values[c] * (k - f)
        return d0 + d1


def measure_latency(func):  # pragma: no cover - thin wrapper
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug("posting_latency_ms", extra={"latency_ms": elapsed})
    return wrapper


metrics = PostingMetrics()

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.metrics_helpers import Histogram


EMAIL_DURATION_BUCKETS = [0.5, 1, 2, 5, 10, 30, 60, 120]


@dataclass
class EmailMetrics:
    enqueued_total: dict[str, int] = field(default_factory=dict)
    sent_total: dict[str, int] = field(default_factory=dict)
    failed_total: dict[tuple[str, str], int] = field(default_factory=dict)
    delivery_duration_seconds: dict[str, Histogram] = field(default_factory=dict)

    def mark_enqueued(self, template_key: str | None) -> None:
        key = template_key or "unknown"
        self.enqueued_total[key] = self.enqueued_total.get(key, 0) + 1

    def mark_sent(self, provider: str, duration_seconds: float | None = None) -> None:
        self.sent_total[provider] = self.sent_total.get(provider, 0) + 1
        if duration_seconds is not None:
            histogram = self.delivery_duration_seconds.get(provider)
            if histogram is None:
                histogram = Histogram(buckets=EMAIL_DURATION_BUCKETS)
                self.delivery_duration_seconds[provider] = histogram
            histogram.observe(duration_seconds)

    def mark_failed(self, provider: str, reason: str, duration_seconds: float | None = None) -> None:
        key = (provider, reason)
        self.failed_total[key] = self.failed_total.get(key, 0) + 1
        if duration_seconds is not None:
            histogram = self.delivery_duration_seconds.get(provider)
            if histogram is None:
                histogram = Histogram(buckets=EMAIL_DURATION_BUCKETS)
                self.delivery_duration_seconds[provider] = histogram
            histogram.observe(duration_seconds)

    def reset(self) -> None:
        self.enqueued_total.clear()
        self.sent_total.clear()
        self.failed_total.clear()
        self.delivery_duration_seconds.clear()


metrics = EmailMetrics()


__all__ = ["EmailMetrics", "metrics"]

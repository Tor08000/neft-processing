from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram
except ModuleNotFoundError:  # pragma: no cover - packaging fallback for scoped tests
    class _MetricStub:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

    def Counter(*args, **kwargs):  # type: ignore[misc]
        return _MetricStub()

    def Gauge(*args, **kwargs):  # type: ignore[misc]
        return _MetricStub()

    def Histogram(*args, **kwargs):  # type: ignore[misc]
        return _MetricStub()

WEBHOOK_DELIVERY_LATENCY_SECONDS = Histogram(
    "webhook_delivery_latency_seconds",
    "Webhook delivery latency in seconds",
    ["endpoint_id", "partner_id"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
)
WEBHOOK_DELIVERY_SLA_BREACHES_TOTAL = Counter(
    "webhook_delivery_sla_breaches_total",
    "Webhook delivery SLA breaches",
    ["endpoint_id", "partner_id"],
)
WEBHOOK_DELIVERY_SUCCESS_RATIO = Gauge(
    "webhook_delivery_success_ratio",
    "Webhook delivery success ratio",
    ["endpoint_id", "partner_id", "window"],
)
WEBHOOK_REPLAY_SCHEDULED_TOTAL = Counter(
    "webhook_replay_scheduled_total",
    "Webhook replay scheduled deliveries",
    ["endpoint_id", "partner_id"],
)
WEBHOOK_PAUSED_ENDPOINTS_TOTAL = Gauge(
    "webhook_paused_endpoints_total",
    "Webhook endpoints paused",
    ["endpoint_id", "partner_id"],
)
WEBHOOK_ALERTS_ACTIVE_TOTAL = Gauge(
    "webhook_alerts_active_total",
    "Webhook alerts active",
    ["endpoint_id", "partner_id", "type", "window"],
)

__all__ = [
    "WEBHOOK_ALERTS_ACTIVE_TOTAL",
    "WEBHOOK_DELIVERY_LATENCY_SECONDS",
    "WEBHOOK_DELIVERY_SLA_BREACHES_TOTAL",
    "WEBHOOK_DELIVERY_SUCCESS_RATIO",
    "WEBHOOK_PAUSED_ENDPOINTS_TOTAL",
    "WEBHOOK_REPLAY_SCHEDULED_TOTAL",
]

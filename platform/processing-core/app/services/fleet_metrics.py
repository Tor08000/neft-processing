from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FleetMetrics:
    ingest_jobs_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    ingest_items_total: Dict[str, int] = field(default_factory=dict)
    limit_breaches_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    anomalies_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    notifications_outbox_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    notifications_delivery_seconds: Dict[str, list[float]] = field(default_factory=dict)
    webhook_responses_total: Dict[str, int] = field(default_factory=dict)
    push_subscriptions_gauge: int = 0
    auto_actions_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    policy_actions_total: Dict[tuple[str, str], int] = field(default_factory=dict)
    auto_block_total: Dict[str, int] = field(default_factory=dict)
    escalations_total: Dict[str, int] = field(default_factory=dict)
    policy_execution_latency_seconds: list[float] = field(default_factory=list)
    alerts_open_gauge: int = 0
    transactions_total: int = 0
    export_requests_total: int = 0

    def mark_ingest_job(self, status: str, provider: str) -> None:
        key = (status, provider)
        self.ingest_jobs_total[key] = self.ingest_jobs_total.get(key, 0) + 1

    def mark_ingest_item(self, result: str, count: int = 1) -> None:
        self.ingest_items_total[result] = self.ingest_items_total.get(result, 0) + count

    def mark_limit_breach(self, breach_type: str, scope: str) -> None:
        key = (breach_type, scope)
        self.limit_breaches_total[key] = self.limit_breaches_total.get(key, 0) + 1

    def mark_anomaly(self, anomaly_type: str, severity: str) -> None:
        key = (anomaly_type, severity)
        self.anomalies_total[key] = self.anomalies_total.get(key, 0) + 1

    def mark_notification_outbox(self, status: str, event_type: str) -> None:
        key = (status, event_type)
        self.notifications_outbox_total[key] = self.notifications_outbox_total.get(key, 0) + 1

    def observe_notification_delivery(self, channel: str, seconds: float) -> None:
        self.notifications_delivery_seconds.setdefault(channel, []).append(seconds)

    def mark_webhook_response(self, status_bucket: str) -> None:
        self.webhook_responses_total[status_bucket] = self.webhook_responses_total.get(status_bucket, 0) + 1

    def adjust_push_subscriptions(self, delta: int) -> None:
        self.push_subscriptions_gauge = max(0, self.push_subscriptions_gauge + delta)

    def mark_auto_action(self, action: str, status: str) -> None:
        key = (action, status)
        self.auto_actions_total[key] = self.auto_actions_total.get(key, 0) + 1

    def mark_policy_action(self, action: str, status: str) -> None:
        key = (action, status)
        self.policy_actions_total[key] = self.policy_actions_total.get(key, 0) + 1

    def mark_auto_block(self, status: str) -> None:
        self.auto_block_total[status] = self.auto_block_total.get(status, 0) + 1

    def mark_escalation(self, status: str) -> None:
        self.escalations_total[status] = self.escalations_total.get(status, 0) + 1

    def observe_policy_execution_latency(self, seconds: float) -> None:
        self.policy_execution_latency_seconds.append(seconds)

    def adjust_alerts_open(self, delta: int) -> None:
        self.alerts_open_gauge = max(0, self.alerts_open_gauge + delta)

    def mark_transaction(self, count: int = 1) -> None:
        self.transactions_total += count

    def mark_export_request(self, count: int = 1) -> None:
        self.export_requests_total += count

    def reset(self) -> None:
        self.ingest_jobs_total.clear()
        self.ingest_items_total.clear()
        self.limit_breaches_total.clear()
        self.anomalies_total.clear()
        self.notifications_outbox_total.clear()
        self.notifications_delivery_seconds.clear()
        self.webhook_responses_total.clear()
        self.push_subscriptions_gauge = 0
        self.auto_actions_total.clear()
        self.policy_actions_total.clear()
        self.auto_block_total.clear()
        self.escalations_total.clear()
        self.policy_execution_latency_seconds.clear()
        self.alerts_open_gauge = 0
        self.transactions_total = 0
        self.export_requests_total = 0


metrics = FleetMetrics()

__all__ = ["FleetMetrics", "metrics"]

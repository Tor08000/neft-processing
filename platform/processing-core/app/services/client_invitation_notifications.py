from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import Session

from app.models.notification_outbox import NotificationOutbox
from app.models.notifications import NotificationPriority, NotificationSubjectType
from app.services.email_provider_runtime import get_email_provider_mode, is_email_degraded

logger = logging.getLogger(__name__)


class _NoopMetric:
    def inc(self, value: float = 1) -> None:
        return None

    def set(self, value: float) -> None:
        return None


_METRICS: tuple[object, object, object, object] | None = None


def _metrics_enabled() -> bool:
    return os.getenv("METRICS_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


def get_metrics() -> tuple[object, object, object, object]:
    global _METRICS
    if _METRICS is not None:
        return _METRICS

    if not _metrics_enabled():
        noop = _NoopMetric()
        _METRICS = (noop, noop, noop, noop)
        return _METRICS

    try:
        from prometheus_client import Counter, Gauge
    except ModuleNotFoundError:
        logger.warning("prometheus_client is unavailable, metrics are disabled")
        noop = _NoopMetric()
        _METRICS = (noop, noop, noop, noop)
        return _METRICS

    _METRICS = (
        Counter("notification_outbox_sent_total", "Notification outbox sent total"),
        Counter("notification_send_attempts_total", "Notification send attempts total"),
        Gauge("notification_outbox_pending", "Notification outbox pending"),
        Gauge("notification_outbox_failed", "Notification outbox failed"),
    )
    return _METRICS


def _backoff(attempts: int) -> timedelta:
    if attempts <= 1:
        return timedelta(seconds=30)
    if attempts == 2:
        return timedelta(minutes=2)
    if attempts == 3:
        return timedelta(minutes=10)
    if attempts == 4:
        return timedelta(hours=1)
    return timedelta(hours=6)


def enqueue_client_invitation_notification(
    db: Session,
    *,
    event_type: str,
    invitation_id: str,
    client_id: str,
    payload: dict,
    template_code: str,
    dedupe_key: str,
) -> NotificationOutbox:
    outbox = NotificationOutbox(
        event_type=event_type,
        subject_type=NotificationSubjectType.CLIENT,
        subject_id=client_id,
        aggregate_type="client_invitation",
        aggregate_id=invitation_id,
        tenant_client_id=client_id,
        template_code=template_code,
        payload=payload,
        priority=NotificationPriority.NORMAL,
        dedupe_key=dedupe_key,
        status="NEW",
    )
    db.add(outbox)
    return outbox


def process_notification_outbox(db: Session, *, limit: int = 50) -> int:
    outbox_sent_total, outbox_attempts_total, outbox_pending, outbox_failed = get_metrics()

    now = datetime.now(timezone.utc)
    rows = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.status == "NEW", NotificationOutbox.next_attempt_at <= now)
        .order_by(NotificationOutbox.created_at.asc())
        .limit(limit)
        .all()
    )

    base_url = os.getenv("INTEGRATION_HUB_URL", "http://integration-hub:8080")
    internal_token = os.getenv("INTEGRATION_HUB_INTERNAL_TOKEN", "")
    endpoint = f"{base_url.rstrip('/')}/api/int/v1/notifications/send"

    mode = get_email_provider_mode()
    sent = 0
    for item in rows:
        item.updated_at = now
        if mode != "integration_hub":
            item.status = "SENT"
            item.last_error = None
            outbox_sent_total.inc()
            sent += 1
            continue
        if is_email_degraded():
            item.status = "NEW"
            item.last_error = "HUB_UNAVAILABLE"
            item.next_attempt_at = now + _backoff(max(1, int(item.attempts or 0)))
            continue

        outbox_attempts_total.inc()
        item.attempts = int(item.attempts or 0) + 1
        try:
            headers = {"Content-Type": "application/json"}
            if internal_token:
                headers["Authorization"] = f"Bearer {internal_token}"
            resp = requests.post(endpoint, json=item.payload or {}, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                item.status = "SENT"
                item.last_error = None
                outbox_sent_total.inc()
                sent += 1
            else:
                raise RuntimeError(f"hub_status_{resp.status_code}")
        except Exception as exc:  # noqa: BLE001
            item.last_error = str(exc)
            if int(item.attempts or 0) >= 10:
                item.status = "FAILED"
            else:
                item.status = "NEW"
                item.next_attempt_at = now + _backoff(int(item.attempts or 0))

    pending = db.query(NotificationOutbox).filter(NotificationOutbox.status == "NEW").count()
    failed = db.query(NotificationOutbox).filter(NotificationOutbox.status == "FAILED").count()
    outbox_pending.set(pending)
    outbox_failed.set(failed)
    db.flush()
    return sent


__all__ = ["enqueue_client_invitation_notification", "process_notification_outbox"]

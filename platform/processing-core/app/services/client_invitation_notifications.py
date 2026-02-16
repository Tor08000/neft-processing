from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import requests
from prometheus_client import Counter, Gauge
from sqlalchemy.orm import Session

from app.models.client_portal import NotificationOutbox

logger = logging.getLogger(__name__)

OUTBOX_SENT_TOTAL = Counter("notification_outbox_sent_total", "Notification outbox sent total")
OUTBOX_ATTEMPTS_TOTAL = Counter("notification_send_attempts_total", "Notification send attempts total")
OUTBOX_PENDING = Gauge("notification_outbox_pending", "Notification outbox pending")
OUTBOX_FAILED = Gauge("notification_outbox_failed", "Notification outbox failed")


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


def enqueue_client_invitation_notification(db: Session, *, event_type: str, invitation_id: str, client_id: str, payload: dict) -> NotificationOutbox:
    outbox = NotificationOutbox(
        event_type=event_type,
        aggregate_type="client_invitation",
        aggregate_id=invitation_id,
        tenant_client_id=client_id,
        payload=payload,
        status="NEW",
    )
    db.add(outbox)
    return outbox


def process_notification_outbox(db: Session, *, limit: int = 50) -> int:
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

    sent = 0
    for item in rows:
        OUTBOX_ATTEMPTS_TOTAL.inc()
        item.attempts = int(item.attempts or 0) + 1
        item.updated_at = now
        try:
            headers = {"Content-Type": "application/json"}
            if internal_token:
                headers["Authorization"] = f"Bearer {internal_token}"
            resp = requests.post(endpoint, json=item.payload or {}, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                item.status = "SENT"
                item.last_error = None
                OUTBOX_SENT_TOTAL.inc()
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
    OUTBOX_PENDING.set(pending)
    OUTBOX_FAILED.set(failed)
    db.flush()
    return sent


__all__ = ["enqueue_client_invitation_notification", "process_notification_outbox"]

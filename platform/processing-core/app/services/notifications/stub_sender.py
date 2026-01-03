from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.fuel import NotificationDeliveryLog

STATUS_ACCEPTED = "ACCEPTED"
STATUS_DELIVERED = "DELIVERED"
STATUS_FAILED = "FAILED"


@dataclass(frozen=True)
class StubSendResult:
    message_id: str
    status: str


def _payload_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def send_stub_message(
    db: Session,
    *,
    tenant_id: str | None,
    channel: str,
    provider: str,
    recipient: str,
    payload: dict[str, Any],
) -> StubSendResult:
    message_id = str(uuid4())
    log = NotificationDeliveryLog(
        tenant_id=tenant_id,
        channel=channel,
        provider=provider,
        message_id=message_id,
        recipient=recipient,
        status=STATUS_ACCEPTED,
        payload_hash=_payload_hash(payload),
    )
    db.add(log)
    db.flush()
    return StubSendResult(message_id=message_id, status=STATUS_ACCEPTED)


def process_stub_delivery_outcomes(
    db: Session,
    *,
    provider: str,
    channel: str,
    delay_ms: int,
    fail_rate: float,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(milliseconds=delay_ms)
    pending = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.provider == provider)
        .filter(NotificationDeliveryLog.channel == channel)
        .filter(NotificationDeliveryLog.status == STATUS_ACCEPTED)
        .filter(NotificationDeliveryLog.created_at <= cutoff)
        .all()
    )
    processed = 0
    for log in pending:
        outcome_failed = random.random() < fail_rate
        log.status = STATUS_FAILED if outcome_failed else STATUS_DELIVERED
        log.error_code = "STUB_DELIVERY_FAILED" if outcome_failed else None
        log.updated_at = now
        processed += 1
    return processed


__all__ = [
    "STATUS_ACCEPTED",
    "STATUS_DELIVERED",
    "STATUS_FAILED",
    "StubSendResult",
    "process_stub_delivery_outcomes",
    "send_stub_message",
]

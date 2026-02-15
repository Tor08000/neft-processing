from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models.event_outbox import EventOutbox
from app.services.event_outbox import compute_backoff
from neft_shared.settings import get_settings

logger = logging.getLogger(__name__)

STREAM_NAME = os.getenv("EVENT_STREAM_NAME", "neft.events")
BATCH_SIZE = int(os.getenv("EVENT_OUTBOX_BATCH_SIZE", "100"))
POLL_INTERVAL_SECONDS = float(os.getenv("EVENT_OUTBOX_POLL_INTERVAL_SECONDS", "2"))
MAX_RETRIES = int(os.getenv("EVENT_OUTBOX_MAX_RETRIES", "5"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _publish_to_stream(redis_client: Redis, event: EventOutbox) -> str:
    payload_json = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return redis_client.xadd(
        STREAM_NAME,
        {
            "event_id": str(event.id),
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "event_type": event.event_type,
            "payload": payload_json,
            "created_at": event.created_at.isoformat() if event.created_at else _now().isoformat(),
        },
    )


def _fetch_batch(db: Session) -> list[EventOutbox]:
    return (
        db.query(EventOutbox)
        .filter(EventOutbox.status == "pending")
        .filter(EventOutbox.next_attempt_at <= _now())
        .order_by(EventOutbox.created_at.asc())
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
        .all()
    )


def _process_event(db: Session, redis_client: Redis, event: EventOutbox) -> None:
    try:
        _publish_to_stream(redis_client, event)
        event.status = "published"
        event.published_at = _now()
        event.error = None
    except Exception as exc:  # noqa: BLE001
        event.retries += 1
        event.error = str(exc)
        if event.retries > MAX_RETRIES:
            event.status = "failed"
        else:
            event.status = "pending"
            event.next_attempt_at = _now() + timedelta(seconds=compute_backoff(event.retries))
        logger.warning(
            "Outbox publish failed",
            extra={"event_id": str(event.id), "event_type": event.event_type, "retries": event.retries},
            exc_info=True,
        )


def run_once() -> int:
    session_factory = get_sessionmaker()
    redis_client = _get_redis()
    with session_factory() as db:
        events = _fetch_batch(db)
        if not events:
            return 0
        for event in events:
            _process_event(db, redis_client, event)
        db.commit()
        return len(events)


def run_forever() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    logger.info("Starting event outbox worker", extra={"stream": STREAM_NAME, "batch_size": BATCH_SIZE})
    while True:
        processed = 0
        try:
            processed = run_once()
        except Exception:  # noqa: BLE001
            logger.exception("Event worker iteration failed")
        if processed == 0:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.event_outbox import EventOutbox


def build_idempotency_key(*, aggregate_type: str, aggregate_id: str, event_type: str) -> str:
    return f"{aggregate_type}:{aggregate_id}:{event_type}"


def publish_event(
    session: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: Mapping[str, object],
    idempotency_key: str | None = None,
) -> EventOutbox:
    event = EventOutbox(
        id=str(uuid4()),
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        event_type=event_type,
        payload=dict(payload),
        idempotency_key=idempotency_key
        or build_idempotency_key(
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
        ),
    )
    session.add(event)
    return event


def compute_backoff(retries: int) -> int:
    schedule = [1, 5, 30, 120, 300]
    index = min(max(retries, 1), len(schedule)) - 1
    return schedule[index]


def utcnow() -> datetime:
    return datetime.utcnow()


__all__ = ["EventOutbox", "build_idempotency_key", "publish_event", "compute_backoff", "utcnow"]

"""Compatibility publisher that persists events to the transactional outbox."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.event_outbox import publish_event


def publish(
    db: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_name: str,
    payload: dict,
) -> None:
    publish_event(
        db,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_name,
        payload=payload,
    )

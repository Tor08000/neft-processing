from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event_outbox import EventOutbox


@dataclass
class EventOutboxMetricsSnapshot:
    pending_total: int = 0
    failed_total: int = 0
    published_total: int = 0
    retry_total: int = 0
    lag_seconds: float = 0.0


def load_event_outbox_metrics(db: Session) -> EventOutboxMetricsSnapshot:
    pending_total = db.query(func.count(EventOutbox.id)).filter(EventOutbox.status == "pending").scalar() or 0
    failed_total = db.query(func.count(EventOutbox.id)).filter(EventOutbox.status == "failed").scalar() or 0
    published_total = db.query(func.count(EventOutbox.id)).filter(EventOutbox.status == "published").scalar() or 0
    retry_total = db.query(func.coalesce(func.sum(EventOutbox.retries), 0)).scalar() or 0

    lag_row = (
        db.query(func.coalesce(func.max(func.extract("epoch", func.now() - EventOutbox.created_at)), 0.0))
        .filter(EventOutbox.status == "pending")
        .one()
    )
    lag_seconds = float(lag_row[0] or 0.0)

    return EventOutboxMetricsSnapshot(
        pending_total=int(pending_total),
        failed_total=int(failed_total),
        published_total=int(published_total),
        retry_total=int(retry_total),
        lag_seconds=max(0.0, lag_seconds),
    )


__all__ = ["EventOutboxMetricsSnapshot", "load_event_outbox_metrics"]

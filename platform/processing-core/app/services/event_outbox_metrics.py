from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA, qualified_table_name


@dataclass
class EventOutboxMetricsSnapshot:
    pending_total: int = 0
    failed_total: int = 0
    published_total: int = 0
    retry_total: int = 0
    lag_seconds: float = 0.0


def _event_outbox_table_name(db: Session) -> str:
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        inspector = inspect(bind)
        if DB_SCHEMA and inspector.has_table("event_outbox", schema=DB_SCHEMA):
            return qualified_table_name("event_outbox", DB_SCHEMA)
        return qualified_table_name("event_outbox")
    return qualified_table_name("event_outbox", DB_SCHEMA)


def _lag_seconds_sql(db: Session, table_name: str) -> str:
    if db.get_bind().dialect.name == "sqlite":
        return (
            "SELECT coalesce(max(strftime('%s', 'now') - strftime('%s', created_at)), 0) "
            f"FROM {table_name} WHERE status = :status"
        )
    return (
        "SELECT coalesce(max(extract(epoch from now() - created_at)), 0.0) "
        f"FROM {table_name} WHERE status = :status"
    )


def load_event_outbox_metrics(db: Session) -> EventOutboxMetricsSnapshot:
    table_name = _event_outbox_table_name(db)
    count_sql = text(f"SELECT count(*) FROM {table_name} WHERE status = :status")
    pending_total = db.execute(count_sql, {"status": "pending"}).scalar() or 0
    failed_total = db.execute(count_sql, {"status": "failed"}).scalar() or 0
    published_total = db.execute(count_sql, {"status": "published"}).scalar() or 0
    retry_total = db.execute(text(f"SELECT coalesce(sum(retries), 0) FROM {table_name}")).scalar() or 0

    lag_seconds = float(
        db.execute(text(_lag_seconds_sql(db, table_name)), {"status": "pending"}).scalar() or 0.0
    )

    return EventOutboxMetricsSnapshot(
        pending_total=int(pending_total),
        failed_total=int(failed_total),
        published_total=int(published_total),
        retry_total=int(retry_total),
        lag_seconds=max(0.0, lag_seconds),
    )


__all__ = ["EventOutboxMetricsSnapshot", "load_event_outbox_metrics"]

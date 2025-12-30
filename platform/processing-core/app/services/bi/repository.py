from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.bi import BiCursor, BiDailyMetric, BiDeclineEvent, BiOrderEvent, BiPayoutEvent


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def get_cursor(db: Session, name: str) -> BiCursor | None:
    return db.query(BiCursor).filter(BiCursor.name == name).one_or_none()


def upsert_cursor(db: Session, name: str, *, last_event_at: datetime | None) -> BiCursor:
    cursor = db.query(BiCursor).filter(BiCursor.name == name).one_or_none()
    if cursor is None:
        cursor = BiCursor(name=name, last_event_at=last_event_at)
        db.add(cursor)
    else:
        cursor.last_event_at = last_event_at
    db.commit()
    db.refresh(cursor)
    return cursor


def upsert_order_events(db: Session, rows: Iterable[dict]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    if _is_postgres(db):
        stmt = pg_insert(BiOrderEvent).values(rows_list)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in BiOrderEvent.__table__.columns
            if col.name != "event_id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["event_id"], set_=update_cols)
        db.execute(stmt)
    else:
        for row in rows_list:
            db.merge(BiOrderEvent(**row))
    db.commit()
    return len(rows_list)


def upsert_payout_events(db: Session, rows: Iterable[dict]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    if _is_postgres(db):
        stmt = pg_insert(BiPayoutEvent).values(rows_list)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in BiPayoutEvent.__table__.columns
            if col.name != "event_id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["event_id"], set_=update_cols)
        db.execute(stmt)
    else:
        for row in rows_list:
            db.merge(BiPayoutEvent(**row))
    db.commit()
    return len(rows_list)


def upsert_decline_events(db: Session, rows: Iterable[dict]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    if _is_postgres(db):
        stmt = pg_insert(BiDeclineEvent).values(rows_list)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in BiDeclineEvent.__table__.columns
            if col.name != "operation_id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=["operation_id"], set_=update_cols)
        db.execute(stmt)
    else:
        for row in rows_list:
            db.merge(BiDeclineEvent(**row))
    db.commit()
    return len(rows_list)


def upsert_daily_metrics(db: Session, rows: Iterable[dict]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    if _is_postgres(db):
        stmt = pg_insert(BiDailyMetric).values(rows_list)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in BiDailyMetric.__table__.columns
            if col.name not in {"id"}
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "date", "scope_type", "scope_id"],
            set_=update_cols,
        )
        db.execute(stmt)
    else:
        for row in rows_list:
            db.merge(BiDailyMetric(**row))
    db.commit()
    return len(rows_list)


def get_latest_event_time(db: Session, model, *, default: datetime | None = None) -> datetime | None:
    value = db.query(func.max(model.occurred_at)).scalar()
    return value or default


__all__ = [
    "get_cursor",
    "get_latest_event_time",
    "upsert_cursor",
    "upsert_daily_metrics",
    "upsert_decline_events",
    "upsert_order_events",
    "upsert_payout_events",
]


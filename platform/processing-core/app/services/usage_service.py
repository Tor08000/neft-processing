from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, insert, select
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def record_usage_event(
    db: Session,
    *,
    org_id: int,
    meter_code: str,
    quantity: Decimal | int,
    source_id: str,
    occurred_at: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> bool:
    if not _table_exists(db, "usage_meters") or not _table_exists(db, "usage_events"):
        logger.warning("usage_event.tables_missing")
        return False

    usage_meters = _table(db, "usage_meters")
    meter = (
        db.execute(select(usage_meters).where(usage_meters.c.code == meter_code)).mappings().first()
    )
    if not meter:
        logger.warning("usage_event.meter_missing", extra={"meter_code": meter_code})
        return False

    usage_events = _table(db, "usage_events")
    existing = (
        db.execute(
            select(usage_events.c.id).where(
                usage_events.c.org_id == org_id,
                usage_events.c.meter_id == meter["id"],
                usage_events.c.meta_json["source_id"].astext == str(source_id),
            )
        )
        .mappings()
        .first()
    )
    if existing:
        return False

    meta_payload = {"source_id": str(source_id)}
    if meta:
        meta_payload.update(meta)

    db.execute(
        insert(usage_events).values(
            org_id=org_id,
            meter_id=meter["id"],
            quantity=_decimal(quantity),
            occurred_at=occurred_at or datetime.now(timezone.utc),
            meta_json=meta_payload,
        )
    )
    return True


__all__ = ["record_usage_event"]

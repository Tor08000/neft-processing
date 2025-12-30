from __future__ import annotations

from datetime import date

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.bi import exports as bi_exports
from app.services.bi import service as bi_service

logger = get_logger(__name__)


@celery_client.task(name="bi.ingest_events")
def ingest_events_task() -> dict[str, dict[str, str | int | None]]:
    session = get_sessionmaker()()
    try:
        results = bi_service.ingest_events(session)
        payload = {
            key: {"inserted": result.inserted, "cursor_at": result.cursor_at.isoformat() if result.cursor_at else None}
            for key, result in results.items()
        }
        session.commit()
        return payload
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("bi.ingest_events_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="bi.aggregate_daily")
def aggregate_daily_task(date_from: date, date_to: date) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        updated = bi_service.aggregate_daily(session, date_from=date_from, date_to=date_to)
        session.commit()
        return {"updated": updated}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("bi.aggregate_daily_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="bi.backfill")
def backfill_task(date_from: date, date_to: date) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = bi_service.backfill(session, date_from=date_from, date_to=date_to)
        session.commit()
        return {"updated": int(result.get("aggregated", 0))}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("bi.backfill_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="bi.generate_export")
def generate_export_task(export_id: str) -> dict[str, str]:
    session = get_sessionmaker()()
    try:
        export = bi_exports.generate_export(session, export_id)
        session.commit()
        return {"export_id": export.id, "status": export.status.value}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("bi.generate_export_failed", extra={"export_id": export_id})
        raise
    finally:
        session.close()


__all__ = [
    "aggregate_daily_task",
    "backfill_task",
    "generate_export_task",
    "ingest_events_task",
]

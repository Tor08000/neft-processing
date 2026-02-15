from __future__ import annotations

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.geo_clickhouse import run_geo_etl

logger = get_logger(__name__)


@celery_client.task(name="geo.clickhouse_sync")
def geo_clickhouse_sync_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = run_geo_etl(session)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("geo.clickhouse_sync_failed")
        raise
    finally:
        session.close()


__all__ = ["geo_clickhouse_sync_task"]

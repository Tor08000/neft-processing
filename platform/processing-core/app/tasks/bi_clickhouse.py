from __future__ import annotations

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.bi.clickhouse import sync_clickhouse

logger = get_logger(__name__)


@celery_client.task(name="bi.clickhouse_sync")
def clickhouse_sync_task() -> dict[str, int | str]:
    session = get_sessionmaker()()
    try:
        result = sync_clickhouse(session)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("bi.clickhouse_sync_failed")
        raise
    finally:
        session.close()


__all__ = ["clickhouse_sync_task"]

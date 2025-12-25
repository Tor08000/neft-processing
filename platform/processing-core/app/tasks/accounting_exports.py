from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.accounting_export.monitoring import check_overdue_batches
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(name="accounting_exports.check_overdue_batches")
def check_overdue_batches_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = check_overdue_batches(session)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("accounting_exports.check_overdue_batches_failed")
        raise
    finally:
        session.close()


__all__ = ["check_overdue_batches_task"]

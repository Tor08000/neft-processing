from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.billing_dunning import auto_suspend_overdue, scan_billing_dunning
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(
    name="billing.dunning_scan",
    bind=True,
    queue="billing",
    max_retries=2,
    default_retry_delay=30,
)
def billing_dunning_scan(self) -> dict:
    session = get_sessionmaker()()
    try:
        stats = scan_billing_dunning(session)
        session.commit()
        return stats
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("billing_dunning.scan_failed", extra={"error": str(exc)})
        raise
    finally:
        session.close()


@celery_client.task(
    name="billing.suspend_overdue",
    bind=True,
    queue="billing",
    max_retries=2,
    default_retry_delay=30,
)
def billing_suspend_overdue(self) -> dict:
    session = get_sessionmaker()()
    try:
        stats = auto_suspend_overdue(session)
        session.commit()
        return stats
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("billing_dunning.suspend_failed", extra={"error": str(exc)})
        raise
    finally:
        session.close()


__all__ = ["billing_dunning_scan", "billing_suspend_overdue"]

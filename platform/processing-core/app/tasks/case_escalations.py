from __future__ import annotations

from datetime import datetime, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.case_escalation_service import evaluate_escalations
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(name="cases.evaluate_escalations")
def evaluate_case_escalations_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = evaluate_escalations(session, now=datetime.now(timezone.utc))
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("cases_escalations_failed")
        raise
    finally:
        session.close()


__all__ = ["evaluate_case_escalations_task"]

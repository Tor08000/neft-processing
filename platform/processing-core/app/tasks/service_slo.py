from __future__ import annotations

from datetime import datetime, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.service_slo import ServiceSlo
from app.services.service_slo import ensure_breach_status, evaluate_slo
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(name="slo.evaluate")
def evaluate_service_slos() -> dict:
    session = get_sessionmaker()()
    now = datetime.now(timezone.utc)
    evaluated = 0
    try:
        slos = session.query(ServiceSlo).filter(ServiceSlo.enabled.is_(True)).all()
        for slo in slos:
            bounds, observation = evaluate_slo(session, slo, now)
            ensure_breach_status(session, slo, bounds, observation, now)
            session.commit()
            evaluated += 1
        return {"status": "ok", "evaluated": evaluated}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("service_slo_evaluation_failed")
        raise
    finally:
        session.close()


__all__ = ["evaluate_service_slos"]

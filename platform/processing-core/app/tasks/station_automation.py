from __future__ import annotations

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.fuel.station_automation import evaluate_station_health, evaluate_station_risk

logger = get_logger(__name__)


@celery_client.task(name="ops.station_health_evaluate")
def station_health_evaluate_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = evaluate_station_health(session)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ops.station_health_evaluate_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="ops.station_risk_evaluate")
def station_risk_evaluate_task() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        result = evaluate_station_risk(session)
        session.commit()
        return result
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ops.station_risk_evaluate_failed")
        raise
    finally:
        session.close()


__all__ = ["station_health_evaluate_task", "station_risk_evaluate_task"]

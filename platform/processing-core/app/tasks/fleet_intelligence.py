from __future__ import annotations

from datetime import datetime, timedelta, timezone

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.fleet_intelligence import jobs

logger = get_logger(__name__)


@celery_client.task(name="fleet_intelligence.compute_daily_aggregates")
def compute_daily_aggregates_task(day_offset: int = 1) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        target_day = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
        result = jobs.run_daily_aggregates(session, day=target_day)
        return {
            "day": int(target_day.strftime("%Y%m%d")),
            "drivers": len(result["drivers"]),
            "vehicles": len(result["vehicles"]),
            "stations": len(result["stations"]),
        }
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fleet_intelligence.daily_aggregates_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="fleet_intelligence.compute_scores")
def compute_scores_task(day_offset: int = 1) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        target_day = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
        result = jobs.run_scores(session, as_of=target_day)
        return {"day": int(target_day.strftime("%Y%m%d")), **result}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fleet_intelligence.compute_scores_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="fleet_intelligence.compute_trends_daily")
def compute_trends_task(day_offset: int = 1) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        target_day = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
        result = jobs.compute_trends_all(session, day=target_day)
        return {"day": int(target_day.strftime("%Y%m%d")), **result}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fleet_intelligence.compute_trends_failed")
        raise
    finally:
        session.close()


__all__ = ["compute_daily_aggregates_task", "compute_scores_task", "compute_trends_task"]

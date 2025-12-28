from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

from neft_shared.logging_setup import get_logger

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.fuel import fraud

logger = get_logger(__name__)


@celery_client.task(name="fraud.compute_station_reputation_daily")
def compute_station_reputation_daily_task(day_offset: int = 1) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        target_day = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
        count = fraud.compute_station_reputation_daily(session, target_day=target_day)
        session.commit()
        return {"day": int(target_day.strftime("%Y%m%d")), "stations": count}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fraud.station_reputation_daily_failed")
        raise
    finally:
        session.close()


@celery_client.task(name="fraud.cleanup_fraud_signals")
def cleanup_fraud_signals_task(retention_days: int = 90) -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        configured = os.getenv("FRAUD_SIGNAL_RETENTION_DAYS")
        retention = int(configured) if configured is not None else retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
        deleted = fraud.cleanup_fraud_signals(session, older_than=cutoff)
        return {"deleted": deleted}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("fraud.cleanup_failed")
        raise
    finally:
        session.close()


__all__ = ["compute_station_reputation_daily_task", "cleanup_fraud_signals_task"]

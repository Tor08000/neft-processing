from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from celery import shared_task
from sqlalchemy import create_engine, text

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

from app.job_evidence import (
    _build_engine_connect_args,
    _resolve_database_url,
    record_job_finish,
    record_job_start,
)

logger = get_logger(__name__)
settings = get_settings()
_database_url = _resolve_database_url()

_engine = create_engine(
    _database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=_build_engine_connect_args(_database_url),
)


@shared_task(bind=True, name="billing.build_daily_summaries")
def build_daily_summaries(self, target_date: str | None = None) -> dict:
    """Aggregate CAPTURE operations for a given date and persist them.

    The date format is YYYY-MM-DD. If omitted, yesterday is used.
    """

    target = (
        datetime.strptime(target_date, "%Y-%m-%d").date()
        if target_date
        else date.today() - timedelta(days=1)
    )
    start = datetime.combine(target, datetime.min.time())
    end = datetime.combine(target, datetime.max.time())

    scheduled_at = datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)
    run_id = record_job_start("billing.build_daily_summaries", scheduled_at, self.request.id)
    started_at = time.monotonic()
    logger.info("[job] started: billing.build_daily_summaries celery_task_id=%s", self.request.id)
    logger.info("Building billing summary for %s", target.isoformat())

    try:
        with _engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT date(created_at) AS op_date,
                           merchant_id,
                           COALESCE(SUM(amount), 0) AS total_amount,
                           COUNT(*) AS operations_count
                    FROM operations
                    WHERE operation_type = 'CAPTURE'
                      AND created_at >= :start
                      AND created_at <= :end
                    GROUP BY op_date, merchant_id
                    ORDER BY op_date
                    """
                ),
                {"start": start, "end": end},
            ).mappings()

            inserted = 0
            for row in rows:
                conn.execute(
                    text(
                        """
                        INSERT INTO billing_summary (
                            id, date, merchant_id, total_captured_amount, operations_count
                        ) VALUES (:id, :date, :merchant_id, :total_amount, :operations_count)
                        ON CONFLICT (date, merchant_id) DO UPDATE
                        SET total_captured_amount = EXCLUDED.total_captured_amount,
                            operations_count = EXCLUDED.operations_count
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "date": row["op_date"],
                        "merchant_id": row["merchant_id"],
                        "total_amount": int(row["total_amount"] or 0),
                        "operations_count": int(row["operations_count"] or 0),
                    },
                )
                inserted += 1

        logger.info("Billing summary built for %s: %s rows", target.isoformat(), inserted)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        record_job_finish(run_id, "SUCCESS")
        logger.info(
            "[job] finished: billing.build_daily_summaries status=SUCCESS duration_ms=%s",
            duration_ms,
        )
        return {"date": target.isoformat(), "rows": inserted}
    except Exception as exc:
        record_job_finish(run_id, "FAILED", error=str(exc))
        logger.exception(
            "[job] failed: billing.build_daily_summaries error=%s", str(exc)
        )
        raise

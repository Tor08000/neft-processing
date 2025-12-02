from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from celery import shared_task
from sqlalchemy import create_engine, text

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()
_engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)


@shared_task(name="clearing.build_daily_batch")
def build_daily_batch(target_date: str | None = None) -> dict:
    target = (
        datetime.strptime(target_date, "%Y-%m-%d").date()
        if target_date
        else date.today() - timedelta(days=1)
    )
    start = datetime.combine(target, datetime.min.time())
    end = datetime.combine(target, datetime.max.time())

    logger.info("Building clearing batches for %s", target.isoformat())
    created = 0

    with _engine.begin() as conn:
        merchants = conn.execute(
            text(
                """
                SELECT DISTINCT merchant_id
                FROM operations
                WHERE operation_type = 'CAPTURE'
                  AND created_at >= :start
                  AND created_at <= :end
                """
            ),
            {"start": start, "end": end},
        ).scalars()

        for merchant_id in merchants:
            captures = conn.execute(
                text(
                    """
                    SELECT operation_id, amount
                    FROM operations
                    WHERE operation_type = 'CAPTURE'
                      AND merchant_id = :merchant_id
                      AND created_at >= :start
                      AND created_at <= :end
                    """
                ),
                {"merchant_id": merchant_id, "start": start, "end": end},
            ).mappings()
            captures_list = list(captures)
            total_amount = sum(int(row["amount"] or 0) for row in captures_list)
            operations_count = len(captures_list)

            batch_id = str(uuid4())
            conn.execute(
                text(
                    """
                    INSERT INTO clearing_batch (
                        id, merchant_id, date_from, date_to, total_amount, operations_count, status
                    ) VALUES (:id, :merchant_id, :date_from, :date_to, :total_amount, :operations_count, 'PENDING')
                    """
                ),
                {
                    "id": batch_id,
                    "merchant_id": merchant_id,
                    "date_from": target,
                    "date_to": target,
                    "total_amount": total_amount,
                    "operations_count": operations_count,
                },
            )

            for row in captures_list:
                conn.execute(
                    text(
                        """
                        INSERT INTO clearing_batch_operation (id, batch_id, operation_id, amount)
                        VALUES (:id, :batch_id, :operation_id, :amount)
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "batch_id": batch_id,
                        "operation_id": row["operation_id"],
                        "amount": int(row["amount"] or 0),
                    },
                )
            created += 1

    return {"date": target.isoformat(), "batches": created}


@shared_task(name="clearing.finalize_billing")
def finalize_billing() -> dict:
    updated = 0
    now = datetime.utcnow()
    with _engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE billing_summary
                SET status = 'FINALIZED', finalized_at = :now
                WHERE status IS NULL OR status != 'FINALIZED'
                """
            ),
            {"now": now},
        )
        updated = result.rowcount or 0
    logger.info("Billing summaries finalized: %s", updated)
    return {"finalized": updated}

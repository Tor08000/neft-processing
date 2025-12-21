from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class BillingJobResult:
    run: BillingJobRun
    metrics: dict[str, Any] | None = None
    duration_ms: int | None = None


class BillingJobRunService:
    """Lifecycle helper for recording billing job executions."""

    def __init__(self, db: Session):
        self.db = db

    def start(
        self,
        job_type: BillingJobType,
        *,
        params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        celery_task_id: str | None = None,
        invoice_id: str | None = None,
        billing_period_id: str | None = None,
    ) -> BillingJobRun:
        run = BillingJobRun(
            job_type=job_type,
            params=params,
            status=BillingJobStatus.STARTED,
            correlation_id=correlation_id,
            celery_task_id=celery_task_id,
            invoice_id=invoice_id,
            billing_period_id=billing_period_id,
            updated_at=datetime.utcnow(),
            attempts=(1 if celery_task_id else 0),
        )
        self.db.add(run)
        self.db.flush()
        logger.info(
            "billing.job.start",
            extra={"job_type": job_type, "params": params, "correlation_id": correlation_id, "celery_task_id": celery_task_id},
        )
        return run

    def succeed(
        self,
        run: BillingJobRun,
        *,
        metrics: dict[str, Any] | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> BillingJobResult:
        run.status = BillingJobStatus.SUCCESS
        run.metrics = metrics
        run.finished_at = datetime.utcnow()
        run.updated_at = run.finished_at
        run.duration_ms = _duration_ms(run)
        if result_ref is not None:
            run.result_ref = result_ref
        self.db.add(run)
        self.db.flush()
        logger.info(
            "billing.job.completed",
            extra={"job_type": run.job_type, "run_id": run.id, "metrics": metrics, "duration_ms": run.duration_ms},
        )
        return BillingJobResult(run=run, metrics=metrics, duration_ms=run.duration_ms)

    def fail(self, run: BillingJobRun, *, error: str) -> BillingJobResult:
        run.status = BillingJobStatus.FAILED
        run.error = error
        run.finished_at = datetime.utcnow()
        run.updated_at = run.finished_at
        run.duration_ms = _duration_ms(run)
        self.db.add(run)
        self.db.flush()
        logger.exception(
            "billing.job.failed",
            extra={"job_type": run.job_type, "run_id": run.id, "error": error, "duration_ms": run.duration_ms},
        )
        return BillingJobResult(run=run, duration_ms=run.duration_ms)

    def heartbeat(self, run: BillingJobRun) -> None:
        run.last_heartbeat_at = datetime.utcnow()
        run.updated_at = run.last_heartbeat_at
        self.db.add(run)
        self.db.flush()


def _duration_ms(run: BillingJobRun) -> int | None:
    """Compute duration between start and finish handling tz-aware/naive values."""

    if not run.started_at or not run.finished_at:
        return None

    start = run.started_at
    end = run.finished_at

    if start.tzinfo and not end.tzinfo:
        end = end.replace(tzinfo=start.tzinfo)
    elif end.tzinfo and not start.tzinfo:
        start = start.replace(tzinfo=end.tzinfo)

    if start.tzinfo and end.tzinfo:
        delta = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    else:
        delta = end - start

    return int(delta.total_seconds() * 1000)

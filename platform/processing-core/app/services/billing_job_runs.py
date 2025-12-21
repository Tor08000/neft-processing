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

    def start(self, job_type: BillingJobType, *, params: dict[str, Any] | None = None) -> BillingJobRun:
        run = BillingJobRun(
            job_type=job_type,
            params=params,
            status=BillingJobStatus.STARTED,
        )
        self.db.add(run)
        self.db.flush()
        logger.info("billing.job.start", extra={"job_type": job_type, "params": params})
        return run

    def succeed(self, run: BillingJobRun, *, metrics: dict[str, Any] | None = None) -> BillingJobResult:
        run.status = BillingJobStatus.SUCCESS
        run.metrics = metrics
        run.finished_at = datetime.utcnow()
        self.db.add(run)
        self.db.flush()
        duration_ms = _duration_ms(run)
        logger.info(
            "billing.job.completed",
            extra={"job_type": run.job_type, "run_id": run.id, "metrics": metrics, "duration_ms": duration_ms},
        )
        return BillingJobResult(run=run, metrics=metrics, duration_ms=duration_ms)

    def fail(self, run: BillingJobRun, *, error: str) -> BillingJobResult:
        run.status = BillingJobStatus.FAILED
        run.error = error
        run.finished_at = datetime.utcnow()
        self.db.add(run)
        self.db.flush()
        duration_ms = _duration_ms(run)
        logger.exception(
            "billing.job.failed",
            extra={"job_type": run.job_type, "run_id": run.id, "error": error, "duration_ms": duration_ms},
        )
        return BillingJobResult(run=run, duration_ms=duration_ms)


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

from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobStatus, BillingJobType
from app.models.clearing import Clearing
from app.services.billing_job_runs import BillingJobRunService
from app.services.clearing_service import generate_clearing_batches_for_date
from app.services.job_locks import advisory_lock, make_lock_token


class ClearingRunInProgress(RuntimeError):
    """Clearing job is already running for the requested date."""


class ClearingRunService:
    """Idempotent clearing run coordinator with advisory locking."""

    def __init__(self, db: Session):
        self.db = db
        self.job_service = BillingJobRunService(db)

    def _load_existing(self, ids: Iterable[str]) -> list[Clearing]:
        if not ids:
            return []
        return list(self.db.query(Clearing).filter(Clearing.id.in_(list(ids))).all())

    async def run(
        self,
        *,
        clearing_date: date,
        idempotency_key: str | None = None,
    ) -> list[Clearing]:
        correlation_id = idempotency_key
        if correlation_id:
            existing = self.job_service.find_by_correlation(BillingJobType.CLEARING_RUN, correlation_id)
            if existing:
                if existing.status == BillingJobStatus.STARTED:
                    raise ClearingRunInProgress(str(existing.id))
                if existing.status == BillingJobStatus.SUCCESS and isinstance(existing.result_ref, dict):
                    batch_ids = existing.result_ref.get("batch_ids") or []
                    return self._load_existing(batch_ids)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        try:
            with txn_context:
                lock_token = make_lock_token("clearing_run", clearing_date.isoformat())
                with advisory_lock(self.db, lock_token) as acquired:
                    if not acquired:
                        raise ClearingRunInProgress(correlation_id or "clearing_run_locked")

                job_run = self.job_service.start(
                    BillingJobType.CLEARING_RUN,
                    params={"clearing_date": clearing_date.isoformat()},
                    correlation_id=correlation_id,
                )

                batches = await generate_clearing_batches_for_date(clearing_date, session=self.db)
                self.job_service.succeed(
                    job_run,
                    metrics={"batches": len(batches), "clearing_date": clearing_date.isoformat()},
                    result_ref={
                        "batch_ids": [batch.id for batch in batches],
                        "clearing_date": clearing_date.isoformat(),
                    },
                )
                return batches
        except Exception as exc:  # noqa: BLE001
            if job_run:
                self.job_service.fail(job_run, error=str(exc))
            raise


__all__ = ["ClearingRunService", "ClearingRunInProgress"]

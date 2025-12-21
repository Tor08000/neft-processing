from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.billing_task_link import BillingTaskLink, BillingTaskStatus, BillingTaskType
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


class BillingTaskLinkService:
    """Persist Celery task ↔ invoice links for idempotency and audit."""

    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self,
        *,
        task_id: str,
        task_name: str,
        job_run_id: str,
        task_type: BillingTaskType,
        status: BillingTaskStatus,
        invoice_id: str | None = None,
        billing_period_id: str | None = None,
        error: str | None = None,
    ) -> BillingTaskLink:
        existing = (
            self.db.query(BillingTaskLink)
            .filter(BillingTaskLink.task_id == task_id)
            .one_or_none()
        )
        now = datetime.now(timezone.utc)

        if existing:
            existing.status = status
            existing.error = error
            if invoice_id:
                existing.invoice_id = invoice_id
            if billing_period_id:
                existing.billing_period_id = billing_period_id
            existing.updated_at = now
            self.db.add(existing)
            return existing

        link = BillingTaskLink(
            task_id=task_id,
            task_name=task_name,
            job_run_id=job_run_id,
            invoice_id=invoice_id,
            billing_period_id=billing_period_id,
            task_type=task_type,
            status=status,
            updated_at=now,
            error=error,
        )
        self.db.add(link)
        return link

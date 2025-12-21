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
        invoice_id: str,
        task_type: BillingTaskType,
        task_id: str,
        status: BillingTaskStatus,
        error: str | None = None,
    ) -> BillingTaskLink:
        existing = (
            self.db.query(BillingTaskLink)
            .filter(BillingTaskLink.invoice_id == invoice_id)
            .filter(BillingTaskLink.task_id == task_id)
            .one_or_none()
        )
        now = datetime.now(timezone.utc)

        if existing:
            existing.status = status
            existing.error = error
            existing.updated_at = now
            self.db.add(existing)
            return existing

        link = BillingTaskLink(
            invoice_id=invoice_id,
            task_type=task_type,
            task_id=task_id,
            status=status,
            updated_at=now,
            error=error,
        )
        self.db.add(link)
        return link

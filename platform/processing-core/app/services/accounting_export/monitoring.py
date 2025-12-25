from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.accounting_export_batch import AccountingExportBatch, AccountingExportState
from app.services.accounting_export.metrics import metrics
from app.services.audit_service import AuditService


def check_overdue_batches(db: Session) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    generate_deadline = now - timedelta(minutes=settings.ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES)
    confirm_deadline = now - timedelta(hours=settings.ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS)

    overdue_created = (
        db.query(AccountingExportBatch)
        .filter(AccountingExportBatch.state == AccountingExportState.CREATED)
        .filter(AccountingExportBatch.created_at < generate_deadline)
        .all()
    )

    unconfirmed = (
        db.query(AccountingExportBatch)
        .filter(AccountingExportBatch.state.in_(
            [AccountingExportState.GENERATED, AccountingExportState.UPLOADED, AccountingExportState.DOWNLOADED]
        ))
        .filter(
            func.coalesce(
                AccountingExportBatch.uploaded_at,
                AccountingExportBatch.generated_at,
                AccountingExportBatch.created_at,
            )
            < confirm_deadline
        )
        .all()
    )

    audit_service = AuditService(db)
    for batch in overdue_created:
        metrics.mark_overdue()
        audit_service.audit(
            event_type="ACCOUNTING_EXPORT_SLA_BREACH",
            entity_type="accounting_export_batch",
            entity_id=str(batch.id),
            action="SLA_BREACH",
            after={
                "batch_id": str(batch.id),
                "period_id": str(batch.billing_period_id),
                "export_type": batch.export_type.value,
                "format": batch.format.value,
                "state": batch.state.value,
                "sla": "generate",
                "deadline_minutes": settings.ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES,
            },
        )

    for batch in unconfirmed:
        metrics.mark_unconfirmed()
        audit_service.audit(
            event_type="ACCOUNTING_EXPORT_SLA_BREACH",
            entity_type="accounting_export_batch",
            entity_id=str(batch.id),
            action="SLA_BREACH",
            after={
                "batch_id": str(batch.id),
                "period_id": str(batch.billing_period_id),
                "export_type": batch.export_type.value,
                "format": batch.format.value,
                "state": batch.state.value,
                "sla": "confirm",
                "deadline_hours": settings.ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS,
            },
        )

    return {
        "overdue": len(overdue_created),
        "unconfirmed": len(unconfirmed),
    }


__all__ = ["check_overdue_batches"]

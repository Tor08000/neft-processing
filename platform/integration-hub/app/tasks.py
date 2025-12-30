from __future__ import annotations

from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import session_scope
from app.models import EdoDocument, EdoDocumentStatus
from app.services.edo_service import poll_document, send_document


@celery_app.task(name="edo.send")
def edo_send(edo_document_id: str) -> None:
    with session_scope() as db:
        send_document(db, edo_document_id)


@celery_app.task(name="edo.poll")
def edo_poll() -> None:
    with session_scope() as db:
        records = (
            db.query(EdoDocument)
            .filter(
                EdoDocument.status.in_(
                    [
                        EdoDocumentStatus.SENT.value,
                        EdoDocumentStatus.DELIVERED.value,
                        EdoDocumentStatus.SIGNED_BY_US.value,
                        EdoDocumentStatus.UPLOADING.value,
                    ]
                )
            )
            .all()
        )
        for record in records:
            poll_document(db, record.id)


@celery_app.task(name="edo.retry")
def edo_retry() -> None:
    now = datetime.now(timezone.utc)
    with session_scope() as db:
        records = (
            db.query(EdoDocument)
            .filter(EdoDocument.status == EdoDocumentStatus.QUEUED.value)
            .filter(EdoDocument.next_retry_at.isnot(None))
            .filter(EdoDocument.next_retry_at <= now)
            .all()
        )
        for record in records:
            send_document(db, record.id)


__all__ = ["edo_send", "edo_poll", "edo_retry"]

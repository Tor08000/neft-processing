from __future__ import annotations

from datetime import datetime, timezone

from neft_integration_hub.celery_app import celery_app
from neft_integration_hub.db import session_scope
from neft_integration_hub.models import EdoDocument, EdoDocumentStatus, WebhookDelivery
from neft_integration_hub.services.webhooks import deliver_webhook, pending_deliveries
from neft_integration_hub.services.edo_service import poll_document, send_document


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


@celery_app.task(name="webhook.deliver")
def webhook_deliver(delivery_id: str) -> None:
    with session_scope() as db:
        delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
        if delivery is None:
            return
        deliver_webhook(db, delivery)


@celery_app.task(name="webhook.retry")
def webhook_retry() -> None:
    with session_scope() as db:
        for delivery in pending_deliveries(db):
            deliver_webhook(db, delivery)


__all__ = ["edo_send", "edo_poll", "edo_retry", "webhook_deliver", "webhook_retry"]

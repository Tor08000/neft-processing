from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.integrations.edo.dtos import EdoStatusRequest
from app.models.edo import EdoDocument, EdoDocumentStatus, EdoOutbox, EdoOutboxStatus
from app.services.edo import EdoService


def dispatch_pending_outbox(session: Session | None = None) -> list[EdoOutbox]:
    close_session = False
    if session is None:
        session = get_sessionmaker()()
        close_session = True
    try:
        service = EdoService(session)
        outbox_items = (
            session.query(EdoOutbox)
            .filter(EdoOutbox.status.in_([EdoOutboxStatus.PENDING, EdoOutboxStatus.FAILED]))
            .filter((EdoOutbox.next_attempt_at.is_(None)) | (EdoOutbox.next_attempt_at <= datetime.now(timezone.utc)))
            .all()
        )
        for item in outbox_items:
            service.dispatch_outbox_item(item)
        return outbox_items
    finally:
        if close_session:
            session.close()


def poll_statuses(session: Session | None = None) -> list[EdoDocument]:
    close_session = False
    if session is None:
        session = get_sessionmaker()()
        close_session = True
    try:
        service = EdoService(session)
        documents = (
            session.query(EdoDocument)
            .filter(EdoDocument.status.in_([EdoDocumentStatus.SENT, EdoDocumentStatus.DELIVERED, EdoDocumentStatus.SENDING]))
            .all()
        )
        for doc in documents:
            if not doc.provider_doc_id:
                continue
            service.refresh_status(
                EdoStatusRequest(provider_doc_id=doc.provider_doc_id, account_id=str(doc.account_id))
            )
        return documents
    finally:
        if close_session:
            session.close()


__all__ = ["dispatch_pending_outbox", "poll_statuses"]

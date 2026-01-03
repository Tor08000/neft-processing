from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from neft_integration_hub.models import EdoStubDocument, EdoStubEvent, EdoStubStatus
from neft_integration_hub.settings import get_settings

settings = get_settings()


def create_stub_document(
    db: Session,
    *,
    document_id: str,
    counterparty: dict,
    payload_ref: str,
    meta: dict | None = None,
) -> EdoStubDocument:
    record = EdoStubDocument(
        document_id=document_id,
        counterparty=counterparty,
        payload_ref=payload_ref,
        status=EdoStubStatus.SENT.value,
        meta=meta,
        last_status_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _append_event(db, record, EdoStubStatus.SENT.value, note="stub_send")
    return record


def get_stub_document(db: Session, edo_document_id: str) -> EdoStubDocument | None:
    record = db.query(EdoStubDocument).filter(EdoStubDocument.id == edo_document_id).first()
    if record:
        _advance_if_due(db, record)
    return record


def simulate_status(
    db: Session,
    edo_document_id: str,
    status: EdoStubStatus,
    *,
    note: str | None = None,
) -> EdoStubDocument | None:
    record = db.query(EdoStubDocument).filter(EdoStubDocument.id == edo_document_id).first()
    if not record:
        return None
    _set_status(db, record, status.value, note=note or "manual_simulate")
    return record


def _append_event(
    db: Session,
    record: EdoStubDocument,
    status: str,
    *,
    note: str | None = None,
    payload: dict | None = None,
) -> None:
    event = EdoStubEvent(
        edo_document_id=record.id,
        status=status,
        note=note,
        payload=payload,
    )
    db.add(event)
    db.commit()


def _set_status(db: Session, record: EdoStubDocument, status: str, *, note: str | None = None) -> None:
    record.status = status
    record.last_status_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    _append_event(db, record, status, note=note)
    db.refresh(record)


def _advance_if_due(db: Session, record: EdoStubDocument) -> None:
    if record.status in {EdoStubStatus.REJECTED.value, EdoStubStatus.SIGNED.value}:
        return
    now = datetime.now(timezone.utc)
    last = record.last_status_at or record.created_at
    elapsed = (now - last).total_seconds()

    if record.status == EdoStubStatus.SENT.value and elapsed >= settings.edo_stub_delivered_after_seconds:
        _set_status(db, record, EdoStubStatus.DELIVERED.value, note="auto_delivered")
        return
    if record.status == EdoStubStatus.DELIVERED.value and elapsed >= settings.edo_stub_signed_after_seconds:
        _set_status(db, record, EdoStubStatus.SIGNED.value, note="auto_signed")


__all__ = ["create_stub_document", "get_stub_document", "simulate_status"]

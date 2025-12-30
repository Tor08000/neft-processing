from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from neft_integration_hub.events import build_event, publish_event
from neft_integration_hub.models import EdoDocument, EdoDocumentStatus
from neft_integration_hub.providers.registry import get_registry
from neft_integration_hub.schemas import DispatchRequest
from neft_integration_hub.settings import get_settings
from neft_integration_hub.storage import S3Storage

settings = get_settings()


EVENT_BY_STATUS = {
    EdoDocumentStatus.SENT.value: "EDO_DOCUMENT_SENT",
    EdoDocumentStatus.DELIVERED.value: "EDO_DOCUMENT_DELIVERED",
    EdoDocumentStatus.SIGNED_BY_COUNTERPARTY.value: "EDO_DOCUMENT_SIGNED_COUNTERPARTY",
    EdoDocumentStatus.REJECTED.value: "EDO_DOCUMENT_REJECTED",
    EdoDocumentStatus.FAILED.value: "EDO_DOCUMENT_FAILED",
}


def dispatch_request(db: Session, payload: DispatchRequest) -> EdoDocument:
    existing = (
        db.query(EdoDocument)
        .filter(EdoDocument.document_id == payload.document_id, EdoDocument.provider == payload.provider)
        .first()
    )
    if existing:
        return existing

    record = EdoDocument(
        document_id=payload.document_id,
        signature_id=payload.signature_id,
        provider=payload.provider,
        status=EdoDocumentStatus.QUEUED.value,
        meta={
            "artifact": payload.artifact.model_dump(),
            "counterparty": payload.counterparty.model_dump(),
            "meta": payload.meta,
            "idempotency_key": payload.idempotency_key,
        },
        last_status_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _publish_status_event(record: EdoDocument, status: str, *, error_code: str | None = None, error_message: str | None = None) -> None:
    event_type = EVENT_BY_STATUS.get(status)
    if not event_type:
        return
    payload = {
        "document_id": record.document_id,
        "signature_id": record.signature_id,
        "provider": record.provider,
        "status": status,
        "provider_message_id": record.provider_message_id,
        "error_code": error_code,
        "error_message": error_message,
    }
    event = build_event(event_type=event_type, payload=payload, correlation_id=record.document_id)
    publish_event(event)


def _next_retry(attempt: int) -> datetime:
    delay = min(300, int(math.pow(2, attempt)))
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def _update_status(db: Session, record: EdoDocument, status: str, *, error: str | None = None) -> None:
    record.status = status
    record.last_status_at = datetime.now(timezone.utc)
    if error:
        record.last_error = error
    db.add(record)
    db.commit()
    db.refresh(record)


def _load_artifact_bytes(record: EdoDocument) -> bytes:
    meta = record.meta or {}
    artifact = meta.get("artifact") or {}
    bucket = artifact.get("bucket")
    object_key = artifact.get("object_key")
    expected_sha = artifact.get("sha256")
    if not bucket or not object_key:
        raise ValueError("missing_artifact")

    storage = S3Storage(bucket=bucket)
    payload = storage.get_bytes(object_key)
    if payload is None:
        raise ValueError("artifact_not_found")

    if expected_sha:
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected_sha:
            raise ValueError("artifact_hash_mismatch")

    return payload


def send_document(db: Session, edo_document_id: str) -> EdoDocument:
    record = db.query(EdoDocument).filter(EdoDocument.id == edo_document_id).first()
    if not record:
        raise ValueError("edo_document_not_found")
    if record.status not in {EdoDocumentStatus.QUEUED.value, EdoDocumentStatus.UPLOADING.value}:
        return record

    try:
        record.status = EdoDocumentStatus.UPLOADING.value
        record.last_status_at = datetime.now(timezone.utc)
        db.add(record)
        db.commit()
        db.refresh(record)

        document_bytes = _load_artifact_bytes(record)
        provider = get_registry().get(record.provider)
        provider_message_id = provider.send(document_bytes, record.meta or {})
        record.provider_message_id = provider_message_id
        _update_status(db, record, EdoDocumentStatus.SENT.value)
        _publish_status_event(record, EdoDocumentStatus.SENT.value)
    except Exception as exc:  # noqa: BLE001
        record.attempt += 1
        record.last_error = str(exc)
        if record.attempt >= settings.edo_max_attempts:
            _update_status(db, record, EdoDocumentStatus.FAILED.value, error=str(exc))
            _publish_status_event(record, EdoDocumentStatus.FAILED.value, error_message=str(exc))
        else:
            record.next_retry_at = _next_retry(record.attempt)
            record.status = EdoDocumentStatus.QUEUED.value
            db.add(record)
            db.commit()
            db.refresh(record)
        return record

    return record


def poll_document(db: Session, edo_document_id: str) -> EdoDocument:
    record = db.query(EdoDocument).filter(EdoDocument.id == edo_document_id).first()
    if not record:
        raise ValueError("edo_document_not_found")
    if record.status in {EdoDocumentStatus.FAILED.value, EdoDocumentStatus.REJECTED.value, EdoDocumentStatus.SIGNED_BY_COUNTERPARTY.value}:
        return record
    if not record.provider_message_id:
        return record

    try:
        provider = get_registry().get(record.provider)
        provider_status = provider.poll(record.provider_message_id)
        new_status = provider_status.status
        if new_status != record.status:
            record.provider_document_id = provider_status.provider_document_id
            _update_status(db, record, new_status, error=provider_status.error_message)
            _publish_status_event(
                record,
                new_status,
                error_code=provider_status.error_code,
                error_message=provider_status.error_message,
            )
    except Exception as exc:  # noqa: BLE001
        record.attempt += 1
        record.last_error = str(exc)
        if record.attempt >= settings.edo_max_attempts:
            _update_status(db, record, EdoDocumentStatus.FAILED.value, error=str(exc))
            _publish_status_event(record, EdoDocumentStatus.FAILED.value, error_message=str(exc))
        else:
            record.next_retry_at = _next_retry(record.attempt)
            db.add(record)
            db.commit()
            db.refresh(record)

    return record


__all__ = ["dispatch_request", "send_document", "poll_document"]

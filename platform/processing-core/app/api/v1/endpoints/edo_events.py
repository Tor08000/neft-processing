from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.documents import DocumentEdoStatus, EdoDocumentStatus, EdoProvider
from app.schemas.edo_events import EdoEventEnvelope
from app.services.audit_service import AuditService, request_context_from_request

router = APIRouter(prefix="/api/v1/edo", tags=["edo"])


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
def handle_edo_event(
    envelope: EdoEventEnvelope,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = envelope.payload
    try:
        provider = EdoProvider(payload.provider)
        status_value = EdoDocumentStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_edo_payload") from exc

    record = (
        db.query(DocumentEdoStatus)
        .filter(DocumentEdoStatus.document_id == str(payload.document_id))
        .filter(DocumentEdoStatus.provider == provider)
        .first()
    )

    before = None
    if record:
        before = {
            "status": record.status.value,
            "provider_message_id": record.provider_message_id,
            "last_error": record.last_error,
        }
        record.status = status_value
        record.signature_id = str(payload.signature_id) if payload.signature_id else record.signature_id
        record.provider_message_id = payload.provider_message_id or record.provider_message_id
        record.last_error = payload.error_message
        record.last_status_at = datetime.now(timezone.utc)
    else:
        record = DocumentEdoStatus(
            document_id=str(payload.document_id),
            signature_id=str(payload.signature_id) if payload.signature_id else None,
            provider=provider,
            status=status_value,
            provider_message_id=payload.provider_message_id,
            last_error=payload.error_message,
            last_status_at=datetime.now(timezone.utc),
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    audit = AuditService(db)
    audit.audit(
        event_type=envelope.event_type,
        entity_type="DOCUMENT_EDO_STATUS",
        entity_id=str(record.id),
        action="STATUS_UPDATED",
        before=before,
        after={
            "status": record.status.value,
            "provider_message_id": record.provider_message_id,
            "last_error": record.last_error,
        },
        external_refs={
            "document_id": str(payload.document_id),
            "signature_id": str(payload.signature_id) if payload.signature_id else None,
            "provider": provider.value,
        },
        request_ctx=request_context_from_request(request),
    )

    return {"received": True, "status": record.status.value, "edo_status_id": str(record.id)}


__all__ = ["router"]

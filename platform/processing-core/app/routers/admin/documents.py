from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.document_chain import compute_ack_hash
from app.services.policy import Action, actor_from_token, audit_access_denied, PolicyEngine, ResourceContext
from app.services.documents_storage import DocumentsStorage

router = APIRouter(prefix="/documents", tags=["documents"])


def _audit_immutability_violation(
    *,
    db: Session,
    document: Document,
    reason: str,
    request: Request,
    token: dict,
    extra: dict | None = None,
) -> None:
    payload = {"reason": reason, "status": document.status.value, "document_type": document.document_type.value}
    if extra:
        payload.update(extra)
    AuditService(db).audit(
        event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
        entity_type="document",
        entity_id=str(document.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after=payload,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )


@router.get("/{document_id}/download")
def download_document_admin(
    document_id: str,
    file_type: DocumentFileType,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> Response:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    file_record = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id)
        .filter(DocumentFile.file_type == file_type)
        .one_or_none()
    )
    if file_record is None:
        raise HTTPException(status_code=404, detail="document_file_not_found")

    storage = DocumentsStorage()
    payload = storage.fetch_bytes(file_record.object_key)
    if not payload:
        raise HTTPException(status_code=404, detail="document_file_not_found")

    extension = "pdf" if file_type == DocumentFileType.PDF else "xlsx"
    filename = f"{document.document_type.value}_v{document.version}.{extension}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    AuditService(db).audit(
        event_type="DOCUMENT_DOWNLOADED",
        entity_type="document",
        entity_id=str(document.id),
        action="READ",
        visibility=AuditVisibility.PUBLIC,
        after={"file_type": file_type.value, "document_hash": file_record.sha256},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return Response(content=payload, media_type=file_record.content_type, headers=headers)


@router.post("/{document_id}/finalize")
def finalize_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    if document.status == DocumentStatus.FINALIZED:
        return {"status": document.status.value}

    actor = actor_from_token(token)
    resource = ResourceContext(
        resource_type="DOCUMENT",
        tenant_id=document.tenant_id,
        client_id=document.client_id,
        status=document.status.value,
    )
    decision = PolicyEngine().check(actor=actor, action=Action.DOCUMENT_FINALIZE, resource=resource)
    if not decision.allowed:
        if decision.reason == "status_not_acknowledged":
            _audit_immutability_violation(
                db=db,
                document=document,
                reason="document_not_acknowledged",
                request=request,
                token=token,
            )
            raise HTTPException(status_code=409, detail="document_not_acknowledged")
        audit_access_denied(
            db,
            actor=actor,
            action=Action.DOCUMENT_FINALIZE,
            resource=resource,
            decision=decision,
            token=token,
        )
        raise HTTPException(status_code=403, detail=decision.reason or "forbidden")

    if document.status != DocumentStatus.ACKNOWLEDGED:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="document_not_acknowledged",
            request=request,
            token=token,
        )
        raise HTTPException(status_code=409, detail="document_not_acknowledged")

    pdf_file = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id)
        .filter(DocumentFile.file_type == DocumentFileType.PDF)
        .one_or_none()
    )
    if pdf_file is None or not pdf_file.sha256:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="document_hash_missing",
            request=request,
            token=token,
        )
        raise HTTPException(status_code=409, detail="document_hash_missing")

    acknowledgement = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.client_id == document.client_id)
        .filter(DocumentAcknowledgement.document_type == document.document_type.value)
        .filter(DocumentAcknowledgement.document_id == str(document.id))
        .one_or_none()
    )
    if acknowledgement is None:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="acknowledgement_missing",
            request=request,
            token=token,
        )
        raise HTTPException(status_code=409, detail="acknowledgement_missing")
    if acknowledgement.document_hash != pdf_file.sha256:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="ack_hash_mismatch",
            request=request,
            token=token,
            extra={"ack_hash": acknowledgement.document_hash, "current_hash": pdf_file.sha256},
        )
        raise HTTPException(status_code=409, detail="ack_hash_mismatch")

    document.status = DocumentStatus.FINALIZED
    db.commit()

    ack_by = acknowledgement.ack_by_user_id or acknowledgement.ack_by_email or ""
    ack_hash = compute_ack_hash(acknowledgement.document_hash, acknowledgement.ack_at, ack_by)
    previous_document_hash = None
    if document.version and document.version > 1:
        previous = (
            db.query(Document)
            .filter(Document.tenant_id == document.tenant_id)
            .filter(Document.client_id == document.client_id)
            .filter(Document.document_type == document.document_type)
            .filter(Document.period_from == document.period_from)
            .filter(Document.period_to == document.period_to)
            .filter(Document.version == document.version - 1)
            .one_or_none()
        )
        if previous:
            prev_file = (
                db.query(DocumentFile)
                .filter(DocumentFile.document_id == previous.id)
                .filter(DocumentFile.file_type == DocumentFileType.PDF)
                .one_or_none()
            )
            previous_document_hash = prev_file.sha256 if prev_file else None

    AuditService(db).audit(
        event_type="DOCUMENT_FINALIZED",
        entity_type="document",
        entity_id=str(document.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "document_type": document.document_type.value,
            "document_hash": pdf_file.sha256,
            "previous_document_hash": previous_document_hash,
            "ack_hash": ack_hash,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return {"status": document.status.value}


@router.post("/{document_id}/void")
def void_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if document.status == DocumentStatus.VOID:
        return {"status": document.status.value}
    if document.status == DocumentStatus.FINALIZED:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="document_finalized",
            request=request,
            token=token,
        )
        raise HTTPException(status_code=409, detail="document_finalized")
    if document.status not in {DocumentStatus.DRAFT, DocumentStatus.ISSUED}:
        _audit_immutability_violation(
            db=db,
            document=document,
            reason="document_status_invalid",
            request=request,
            token=token,
        )
        raise HTTPException(status_code=409, detail="document_status_invalid")

    document.status = DocumentStatus.VOID
    document.cancelled_at = document.cancelled_at or datetime.now(timezone.utc)
    db.commit()

    pdf_file = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id)
        .filter(DocumentFile.file_type == DocumentFileType.PDF)
        .one_or_none()
    )
    AuditService(db).audit(
        event_type="DOCUMENT_VOIDED",
        entity_type="document",
        entity_id=str(document.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "document_type": document.document_type.value,
            "document_hash": pdf_file.sha256 if pdf_file else None,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return {"status": document.status.value}

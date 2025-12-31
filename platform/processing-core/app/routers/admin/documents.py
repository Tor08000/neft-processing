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
from app.models.legal_integrations import DocumentSignature, DocumentSignatureStatus
from app.schemas.admin.document_signing import (
    DocumentSignRequest,
    DocumentSignResponse,
    DocumentSignatureListResponse,
    DocumentSignatureOut,
    DocumentSignatureVerifyResponse,
)
from app.services.legal_integrations.service import LegalIntegrationsService
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.document_chain import compute_ack_hash
from app.services.legal_integrations.errors import ProviderNotConfigured
from app.services.policy import Action, actor_from_token, audit_access_denied, PolicyEngine, ResourceContext
from app.services.documents_storage import DocumentsStorage
from app.services.document_signing import DocumentSigningService
from app.services.legal_graph import GraphContext, LegalGraphBuilder, LegalGraphSnapshotService
from app.models.legal_graph import LegalGraphSnapshotScopeType

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


def _signature_to_schema(signature: DocumentSignature) -> DocumentSignatureOut:
    return DocumentSignatureOut(
        id=str(signature.id),
        document_id=str(signature.document_id),
        version=signature.version,
        provider=signature.provider,
        request_id=signature.request_id,
        status=signature.status.value if signature.status else "UNKNOWN",
        input_object_key=signature.input_object_key,
        input_sha256=signature.input_sha256,
        signed_object_key=signature.signed_object_key,
        signed_sha256=signature.signed_sha256,
        signature_object_key=signature.signature_object_key,
        signature_sha256=signature.signature_sha256,
        attempt=signature.attempt,
        error_code=signature.error_code,
        error_message=signature.error_message,
        started_at=signature.started_at,
        finished_at=signature.finished_at,
        meta=signature.meta,
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

    extension = {
        DocumentFileType.PDF: "pdf",
        DocumentFileType.XLSX: "xlsx",
        DocumentFileType.SIG: "sig",
        DocumentFileType.P7S: "p7s",
        DocumentFileType.CERT: "cer",
        DocumentFileType.EDI_XML: "xml",
    }.get(file_type, "bin")
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


@router.post("/{document_id}/sign/request", response_model=DocumentSignResponse)
def request_document_signing(
    document_id: str,
    payload: DocumentSignRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> DocumentSignResponse:
    service = DocumentSigningService(db)
    try:
        result = service.request_sign(
            document_id=document_id,
            provider=payload.provider,
            meta=payload.meta,
            idempotency_key=payload.idempotency_key,
            request=request,
            token=token,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="sign_failed") from exc

    return DocumentSignResponse(signature=_signature_to_schema(result.signature))


@router.get("/{document_id}/signatures", response_model=DocumentSignatureListResponse)
def list_document_signatures(
    document_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> DocumentSignatureListResponse:
    _ = token
    signatures = (
        db.query(DocumentSignature)
        .filter(DocumentSignature.document_id == document_id)
        .order_by(DocumentSignature.version.desc(), DocumentSignature.attempt.desc())
        .all()
    )
    return DocumentSignatureListResponse(items=[_signature_to_schema(signature) for signature in signatures])


@router.post("/{document_id}/signatures/{signature_id}/verify", response_model=DocumentSignatureVerifyResponse)
def verify_document_signature(
    document_id: str,
    signature_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> DocumentSignatureVerifyResponse:
    service = DocumentSigningService(db)
    try:
        result = service.verify_signature(
            document_id=document_id,
            signature_id=signature_id,
            request=request,
            token=token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="verify_failed") from exc

    return DocumentSignatureVerifyResponse(
        signature=_signature_to_schema(result.signature),
        verified=result.verified,
        status=result.status,
    )


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
    legal_service = LegalIntegrationsService(db)
    legal_config = legal_service.resolve_config(tenant_id=document.tenant_id, client_id=document.client_id)
    decision_action = (
        DecisionAction.DOCUMENT_FINALIZE_WITH_SIGNATURE
        if legal_config.require_signature_for_finalize
        else DecisionAction.DOCUMENT_FINALIZE
    )
    decision_context = DecisionContext(
        tenant_id=document.tenant_id,
        client_id=document.client_id,
        actor_type="ADMIN",
        action=decision_action,
        amount=0,
        history={},
        metadata={
            "document_acknowledged": document.status == DocumentStatus.ACKNOWLEDGED,
            "actor_roles": actor.roles,
            "subject_id": str(document.id),
        },
    )
    risk_decision = DecisionEngine(db).evaluate(decision_context)
    if risk_decision.outcome != DecisionOutcome.ALLOW:
        raise HTTPException(
            status_code=403,
            detail={"reason": "risk_decline", "explain": risk_decision.explain},
        )
    policy_action = (
        Action.DOCUMENT_FINALIZE_WITH_SIGNATURE
        if legal_config.require_signature_for_finalize
        else Action.DOCUMENT_FINALIZE
    )
    decision = PolicyEngine().check(actor=actor, action=policy_action, resource=resource)
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

    if legal_config.require_signature_for_finalize:
        signature = (
            db.query(DocumentSignature)
            .filter(DocumentSignature.document_id == document.id)
            .filter(
                (DocumentSignature.verified.is_(True))
                | (DocumentSignature.status == DocumentSignatureStatus.VERIFIED)
            )
            .one_or_none()
        )
        if signature is None:
            _audit_immutability_violation(
                db=db,
                document=document,
                reason="signature_missing",
                request=request,
                token=token,
            )
            raise HTTPException(status_code=409, detail="signature_missing")

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

    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    graph_context = GraphContext(tenant_id=document.tenant_id, request_ctx=request_ctx)
    LegalGraphBuilder(db, context=graph_context).ensure_document_graph(document)
    LegalGraphSnapshotService(db, request_ctx=request_ctx).create_snapshot(
        tenant_id=document.tenant_id,
        scope_type=LegalGraphSnapshotScopeType.DOCUMENT,
        scope_ref_id=str(document.id),
        depth=3,
        actor_ctx=request_ctx,
    )
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
        request_ctx=request_ctx,
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

    signature_exists = (
        db.query(DocumentSignature)
        .filter(DocumentSignature.document_id == document.id)
        .first()
        is not None
    )
    if signature_exists:
        actor = actor_from_token(token)
        resource = ResourceContext(
            resource_type="DOCUMENT",
            tenant_id=document.tenant_id,
            client_id=document.client_id,
            status=document.status.value,
        )
        decision = PolicyEngine().check(actor=actor, action=Action.DOCUMENT_VOID_AFTER_SIGNING, resource=resource)
        if not decision.allowed:
            audit_access_denied(
                db,
                actor=actor,
                action=Action.DOCUMENT_VOID_AFTER_SIGNING,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise HTTPException(status_code=403, detail=decision.reason or "forbidden")

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
@router.post("/{document_id}/send-signing")
def send_document_for_signing(
    document_id: str,
    request: Request,
    provider: str | None = None,
    override_risk: bool = False,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    service = LegalIntegrationsService(db)
    try:
        envelope = service.send_document_for_signing(
            document_id=document_id,
            provider_override=provider,
            token=token,
            request=request,
            override_risk=override_risk,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "document_not_found":
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=409, detail=detail)
    except ProviderNotConfigured:
        raise HTTPException(status_code=409, detail="provider_not_configured")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {"envelope_id": envelope.envelope_id, "provider": envelope.provider, "status": envelope.status.value}


@router.post("/{document_id}/send-edo")
def send_document_for_edo(
    document_id: str,
    request: Request,
    provider: str | None = None,
    override_risk: bool = False,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    service = LegalIntegrationsService(db)
    try:
        envelope = service.send_document_for_signing(
            document_id=document_id,
            provider_override=provider,
            token=token,
            request=request,
            override_risk=override_risk,
            use_edo=True,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "document_not_found":
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=409, detail=detail)
    except ProviderNotConfigured:
        raise HTTPException(status_code=409, detail="provider_not_configured")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {"envelope_id": envelope.envelope_id, "provider": envelope.provider, "status": envelope.status.value}

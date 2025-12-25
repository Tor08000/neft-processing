from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import (
    ClosingPackage,
    ClosingPackageStatus,
    Document,
    DocumentFile,
    DocumentFileType,
    DocumentStatus,
    DocumentType,
)
from app.schemas.closing_documents import (
    ClosingPackageAckResponse,
    ClientDocumentListResponse,
    ClientDocumentSummary,
    DocumentAcknowledgementResponse,
)
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
from app.services.documents_storage import DocumentsStorage

router = APIRouter(prefix="/api/v1/client", tags=["client-documents"])


def _ensure_client_context(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")
    return str(client_id)


def _ensure_tenant_context(token: dict) -> int:
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Missing tenant context")
    return int(tenant_id)


def _ensure_client_action_allowed(token: dict) -> None:
    allowed_roles = {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"}
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    if not allowed_roles.intersection({str(role) for role in roles}):
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/documents", response_model=ClientDocumentListResponse)
def list_documents(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    document_type: str | None = Query(None, alias="type"),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ClientDocumentListResponse:
    client_id = _ensure_client_context(token)

    query = db.query(Document).filter(Document.client_id == client_id)
    if date_from:
        query = query.filter(Document.period_from >= date_from)
    if date_to:
        query = query.filter(Document.period_to <= date_to)
    if document_type:
        try:
            parsed_type = DocumentType(document_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_document_type") from exc
        query = query.filter(Document.document_type == parsed_type)
    if status:
        try:
            parsed_status = DocumentStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_document_status") from exc
        query = query.filter(Document.status == parsed_status)

    total = query.count()
    items = (
        query.order_by(desc(Document.period_from), desc(Document.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    document_ids = [item.id for item in items]
    pdf_hashes: dict[str, str] = {}
    if document_ids:
        pdf_files = (
            db.query(DocumentFile)
            .filter(DocumentFile.document_id.in_(document_ids))
            .filter(DocumentFile.file_type == DocumentFileType.PDF)
            .all()
        )
        pdf_hashes = {str(file.document_id): file.sha256 for file in pdf_files}

    return ClientDocumentListResponse(
        items=[
            ClientDocumentSummary(
                id=str(item.id),
                document_type=item.document_type.value,
                status=item.status.value,
                period_from=item.period_from,
                period_to=item.period_to,
                version=item.version,
                number=item.number,
                created_at=item.created_at,
                pdf_hash=pdf_hashes.get(str(item.id)),
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    file_type: DocumentFileType,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    client_id = _ensure_client_context(token)
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    if document.client_id != client_id:
        raise HTTPException(status_code=403, detail="forbidden")

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
        after={"file_type": file_type.value},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return Response(content=payload, media_type=file_record.content_type, headers=headers)


@router.post("/documents/{document_id}/ack", response_model=DocumentAcknowledgementResponse, status_code=201)
def acknowledge_document(
    document_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> DocumentAcknowledgementResponse:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)
    tenant_id = _ensure_tenant_context(token)

    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    if document.client_id != client_id:
        raise HTTPException(status_code=403, detail="forbidden")

    existing = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.client_id == client_id)
        .filter(DocumentAcknowledgement.document_type == document.document_type.value)
        .filter(DocumentAcknowledgement.document_id == str(document.id))
        .one_or_none()
    )
    if existing:
        return DocumentAcknowledgementResponse(
            acknowledged=True,
            ack_at=existing.ack_at,
            document_type=existing.document_type,
            document_object_key=existing.document_object_key,
            document_hash=existing.document_hash,
        )

    decision_context = DecisionContext(
        tenant_id=tenant_id,
        client_id=client_id,
        actor_type="CLIENT",
        action=DecisionAction.DOCUMENT_FINALIZE,
        invoice_id=str(document.id),
        history={},
        metadata={
            "document_type": document.document_type.value,
            "document_status": document.status.value if document.status else None,
            "document_acknowledged": True,
            "actor_roles": token.get("roles", []),
        },
    )
    decision = DecisionEngine(db).evaluate(decision_context)
    if decision.outcome != "ALLOW":
        raise HTTPException(status_code=403, detail=f"decision_{decision.outcome.lower()}")

    ack_at = datetime.now(timezone.utc)
    document.status = DocumentStatus.ACKNOWLEDGED
    document.ack_at = ack_at

    pdf_file = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id)
        .filter(DocumentFile.file_type == DocumentFileType.PDF)
        .one_or_none()
    )
    acknowledgement = DocumentAcknowledgement(
        tenant_id=tenant_id,
        client_id=client_id,
        document_type=document.document_type.value,
        document_id=str(document.id),
        document_object_key=pdf_file.object_key if pdf_file else None,
        document_hash=pdf_file.sha256 if pdf_file else None,
        ack_by_user_id=token.get("user_id") or token.get("sub"),
        ack_by_email=token.get("email"),
        ack_method="UI",
        ack_at=ack_at,
    )
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)

    AuditService(db).audit(
        event_type="DOCUMENT_ACKNOWLEDGED",
        entity_type="document",
        entity_id=str(document.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after={"document_type": document.document_type.value, "ack_at": acknowledgement.ack_at},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return DocumentAcknowledgementResponse(
        acknowledged=True,
        ack_at=acknowledgement.ack_at,
        document_type=acknowledgement.document_type,
        document_object_key=acknowledgement.document_object_key,
        document_hash=acknowledgement.document_hash,
    )


@router.post("/closing-packages/{package_id}/ack", response_model=ClosingPackageAckResponse)
def acknowledge_closing_package(
    package_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClosingPackageAckResponse:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)

    package = db.query(ClosingPackage).filter(ClosingPackage.id == package_id).one_or_none()
    if package is None:
        raise HTTPException(status_code=404, detail="closing_package_not_found")
    if package.client_id != client_id:
        raise HTTPException(status_code=403, detail="forbidden")

    if package.status == ClosingPackageStatus.ACKNOWLEDGED:
        return ClosingPackageAckResponse(acknowledged=True, ack_at=package.ack_at)

    package.status = ClosingPackageStatus.ACKNOWLEDGED
    package.ack_at = datetime.now(timezone.utc)
    db.commit()

    AuditService(db).audit(
        event_type="CLOSING_PACKAGE_ACKNOWLEDGED",
        entity_type="closing_package",
        entity_id=str(package.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after={"status": package.status.value, "ack_at": package.ack_at},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return ClosingPackageAckResponse(acknowledged=True, ack_at=package.ack_at)

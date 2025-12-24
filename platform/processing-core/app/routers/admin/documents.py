from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.documents import Document, DocumentFile, DocumentFileType
from app.services.audit_service import AuditService, request_context_from_request
from app.services.documents_storage import DocumentsStorage

router = APIRouter(prefix="/documents", tags=["documents"])


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
        after={"file_type": file_type.value},
        request_ctx=request_context_from_request(request, token=token),
    )

    return Response(content=payload, media_type=file_record.content_type, headers=headers)


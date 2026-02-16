from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import AdminInboundDocumentCreateIn, DocumentFileOut, DocumentOut
from app.domains.documents.service import DocumentsService
from app.domains.documents.storage import DocumentsStorage
from app.domains.documents.timeline_service import TimelineRequestContext

router = APIRouter(prefix="/api/core/admin", tags=["admin-documents-v1"])
_ALLOWED_ROLES = {"ADMIN", "PLATFORM_ADMIN", "SUPERADMIN"}


def _service(db: Session = Depends(get_db)) -> DocumentsService:
    return DocumentsService(repo=DocumentsRepository(db=db), storage=DocumentsStorage.from_env())


def _timeline_request_context(request: Request) -> TimelineRequestContext:
    return TimelineRequestContext(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


def _ensure_admin_role(token: dict) -> None:
    roles = set(token.get("roles") or [])
    role = token.get("role")
    if role:
        roles.add(role)
    if not roles.intersection(_ALLOWED_ROLES):
        raise HTTPException(status_code=403, detail="forbidden")


@router.post("/clients/{client_id}/documents", response_model=DocumentOut, status_code=201)
def create_admin_inbound_document(
    client_id: str,
    payload: AdminInboundDocumentCreateIn,
    request: Request,
    token: dict = Depends(require_admin_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentOut:
    _ensure_admin_role(token)
    return svc.create_inbound_document_by_admin(
        client_id=client_id,
        data=payload,
        actor_user_id=token.get("user_id") or token.get("sub"),
        request_context=_timeline_request_context(request),
    )


@router.post("/documents/{document_id}/files", response_model=DocumentFileOut)
async def upload_admin_inbound_document_file(
    document_id: str,
    file: UploadFile = File(...),
    request: Request | None = None,
    token: dict = Depends(require_admin_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentFileOut:
    _ensure_admin_role(token)
    return await svc.attach_file_admin_inbound(
        document_id=document_id,
        upload_file=file,
        actor_user_id=token.get("user_id") or token.get("sub"),
        request_context=_timeline_request_context(request) if request else None,
    )

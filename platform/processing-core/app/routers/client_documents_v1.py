from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.domains.documents.models import DocumentDirection
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import DocumentCreateIn, DocumentDetailsResponse, DocumentFileOut, DocumentOut, DocumentsListResponse
from app.domains.documents.service import DocumentsService
from app.domains.documents.storage import DocumentsStorage
from app.domains.documents.timeline_schemas import TimelineEventOut
from app.domains.documents.timeline_service import TimelineRequestContext

router = APIRouter(prefix="/api/core/client/documents", tags=["client-documents"])


def _client_id_from_token(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="client_not_bound")
    return str(client_id)


def _service(db: Session = Depends(get_db)) -> DocumentsService:
    return DocumentsService(repo=DocumentsRepository(db=db), storage=DocumentsStorage.from_env())


def _timeline_request_context(request: Request) -> TimelineRequestContext:
    return TimelineRequestContext(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("", response_model=DocumentsListResponse)
def list_client_documents(
    token: dict = Depends(client_portal_user),
    direction: str = Query("inbound"),
    status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at_desc"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    svc: DocumentsService = Depends(_service),
) -> DocumentsListResponse:
    if sort != "created_at_desc":
        raise HTTPException(status_code=400, detail="unsupported_sort")

    normalized_direction = direction.lower().strip()
    if normalized_direction not in {"inbound", "outbound"}:
        raise HTTPException(status_code=400, detail="invalid_direction")

    return svc.list_documents(
        client_id=_client_id_from_token(token),
        direction=DocumentDirection.INBOUND if normalized_direction == "inbound" else DocumentDirection.OUTBOUND,
        status=status,
        q=q,
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=DocumentOut, status_code=201)
def create_client_outbound_document(
    payload: DocumentCreateIn,
    request: Request | None = None,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentOut:
    return svc.create_outbound_draft(
        client_id=_client_id_from_token(token),
        data=payload,
        actor_user_id=token.get("user_id") or token.get("sub"),
        request_context=_timeline_request_context(request) if request else None,
    )


@router.post("/{document_id}/upload", response_model=DocumentFileOut, status_code=201)
async def upload_document_file(
    document_id: str,
    file: UploadFile = File(...),
    request: Request | None = None,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentFileOut:
    return await svc.attach_file(
        client_id=_client_id_from_token(token),
        document_id=document_id,
        upload_file=file,
        actor_user_id=token.get("user_id") or token.get("sub"),
        request_context=_timeline_request_context(request) if request else None,
    )


@router.post("/{document_id}/submit", response_model=DocumentOut)
def submit_client_document(
    document_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentOut:
    return svc.submit_ready_to_send(
        client_id=_client_id_from_token(token),
        document_id=document_id,
        actor_user_id=token.get("user_id") or token.get("sub"),
        request_context=_timeline_request_context(request),
    )


@router.get("/{document_id}/timeline", response_model=list[TimelineEventOut])
def get_client_document_timeline(
    document_id: str,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> list[TimelineEventOut]:
    return svc.list_timeline_events(client_id=_client_id_from_token(token), document_id=document_id)


@router.get("/{document_id}", response_model=DocumentDetailsResponse)
def get_client_document(
    document_id: str,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentDetailsResponse:
    document = svc.get_document_with_files(client_id=_client_id_from_token(token), document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    return document




@router.get("/{document_id}/files", response_model=list[DocumentFileOut])
def list_client_document_files(
    document_id: str,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> list[DocumentFileOut]:
    document = svc.get_document_with_files(client_id=_client_id_from_token(token), document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    return document.files

@router.get("/files/{file_id}/download")
def download_client_document_file(
    file_id: str,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
):
    item = svc.get_file_for_download(client_id=_client_id_from_token(token), file_id=file_id)
    if item is None:
        raise HTTPException(status_code=404, detail="document_file_not_found")
    if svc.storage is None:
        raise RuntimeError("documents_storage_not_configured")
    stream = svc.storage.get_object_stream(item.file.storage_key)
    headers = {"Content-Disposition": f'attachment; filename="{item.file.filename}"'}
    return StreamingResponse(stream, media_type=item.file.mime, headers=headers)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.domains.documents.models import DocumentDirection
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.schemas import DocumentDetailsResponse, DocumentsListResponse
from app.domains.documents.service import DocumentsService

router = APIRouter(prefix="/api/core/client/documents", tags=["client-documents"])


def _client_id_from_token(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="client_not_bound")
    return str(client_id)


def _service(db: Session = Depends(get_db)) -> DocumentsService:
    return DocumentsService(repo=DocumentsRepository(db=db))


@router.get("", response_model=DocumentsListResponse)
def list_client_documents(
    token: dict = Depends(client_portal_user),
    direction: str = Query("inbound"),
    status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at_desc"),
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
    )


@router.get("/{document_id}", response_model=DocumentDetailsResponse)
def get_client_document(
    document_id: str,
    token: dict = Depends(client_portal_user),
    svc: DocumentsService = Depends(_service),
) -> DocumentDetailsResponse:
    document = svc.get_document(client_id=_client_id_from_token(token), document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    return document

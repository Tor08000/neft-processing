from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.legal_acceptance import LegalAcceptance, LegalSubjectType
from app.models.legal_document import LegalDocument, LegalDocumentStatus
from app.schemas.legal import (
    LegalAcceptanceListResponse,
    LegalAcceptanceResponse,
    LegalDocumentCreateRequest,
    LegalDocumentListResponse,
    LegalDocumentResponse,
    LegalDocumentUpdateRequest,
)
from app.services.audit_service import request_context_from_request
from app.services.legal import LegalService


router = APIRouter(prefix="/legal", tags=["admin-legal"])


_ALLOWED_LEGAL_ROLES = {"SUPERADMIN", "PLATFORM_ADMIN", "LEGAL_ADMIN"}


def _ensure_legal_admin(token: dict) -> None:
    roles = token.get("roles") or []
    role = token.get("role")
    if role:
        roles = [*roles, role]
    normalized = {str(item).upper() for item in roles}
    if not normalized.intersection(_ALLOWED_LEGAL_ROLES):
        raise HTTPException(status_code=403, detail="legal_admin_required")


@router.post("/documents", response_model=LegalDocumentResponse)
def create_document(
    payload: LegalDocumentCreateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalDocumentResponse:
    _ensure_legal_admin(token)
    service = LegalService(db)
    document = service.create_document(
        payload=payload.model_dump(),
        actor_id=token.get("user_id") or token.get("sub"),
        request_ctx=request_context_from_request(request, token=token),
    )
    db.commit()
    return _document_response(document)


@router.put("/documents/{document_id}", response_model=LegalDocumentResponse)
def update_document(
    document_id: str,
    payload: LegalDocumentUpdateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalDocumentResponse:
    _ensure_legal_admin(token)
    document = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="legal_document_not_found")
    if document.status != LegalDocumentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="legal_document_not_draft")
    service = LegalService(db)
    document = service.update_document(
        document=document,
        payload=payload.model_dump(),
        request_ctx=request_context_from_request(request, token=token),
    )
    db.commit()
    return _document_response(document)


@router.post("/documents/{document_id}/publish", response_model=LegalDocumentResponse)
def publish_document(
    document_id: str,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalDocumentResponse:
    _ensure_legal_admin(token)
    document = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="legal_document_not_found")
    service = LegalService(db)
    document = service.publish_document(
        document=document,
        request_ctx=request_context_from_request(request, token=token),
    )
    db.commit()
    return _document_response(document)


@router.get("/documents", response_model=LegalDocumentListResponse)
def list_documents(
    code: str | None = Query(None),
    status: str | None = Query(None),
    locale: str | None = Query(None),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalDocumentListResponse:
    _ensure_legal_admin(token)
    query = db.query(LegalDocument)
    if code:
        query = query.filter(LegalDocument.code == code)
    if locale:
        query = query.filter(LegalDocument.locale == locale)
    if status:
        query = query.filter(LegalDocument.status == LegalDocumentStatus(status))
    query = query.order_by(LegalDocument.code.asc(), LegalDocument.version.desc())
    documents = query.all()
    return LegalDocumentListResponse(items=[_document_response(doc) for doc in documents])


@router.get("/acceptances", response_model=LegalAcceptanceListResponse)
def list_acceptances(
    subject_type: LegalSubjectType | None = Query(None),
    subject_id: str | None = Query(None),
    document_code: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalAcceptanceListResponse:
    _ensure_legal_admin(token)
    query = db.query(LegalAcceptance)
    if subject_type:
        query = query.filter(LegalAcceptance.subject_type == subject_type)
    if subject_id:
        query = query.filter(LegalAcceptance.subject_id == subject_id)
    if document_code:
        query = query.filter(LegalAcceptance.document_code == document_code)
    if date_from:
        query = query.filter(LegalAcceptance.accepted_at >= date_from)
    if date_to:
        query = query.filter(LegalAcceptance.accepted_at <= date_to)
    acceptances = query.order_by(LegalAcceptance.accepted_at.desc()).all()
    return LegalAcceptanceListResponse(items=[_acceptance_response(item) for item in acceptances])


def _document_response(document: LegalDocument) -> LegalDocumentResponse:
    return LegalDocumentResponse(
        id=str(document.id),
        code=document.code,
        version=document.version,
        title=document.title,
        locale=document.locale,
        effective_from=document.effective_from,
        status=document.status.value,
        content_type=document.content_type.value,
        content=document.content,
        content_hash=document.content_hash,
        published_at=document.published_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _acceptance_response(item: LegalAcceptance) -> LegalAcceptanceResponse:
    return LegalAcceptanceResponse(
        id=str(item.id),
        subject_type=item.subject_type.value,
        subject_id=item.subject_id,
        document_code=item.document_code,
        document_version=item.document_version,
        document_locale=item.document_locale,
        accepted_at=item.accepted_at,
        ip=item.ip,
        user_agent=item.user_agent,
        acceptance_hash=item.acceptance_hash,
        signature=item.signature,
        meta=item.meta,
    )


__all__ = ["router"]

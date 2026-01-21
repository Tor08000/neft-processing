from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.legal_acceptance import LegalSubjectType
from app.models.legal_document import LegalDocumentStatus
from app.schemas.legal import LegalAcceptRequest, LegalDocumentResponse, LegalRequiredResponse
from app.security.rbac.principal import Principal, get_portal_principal, principal_context
from app.services.audit_service import request_context_from_request
from app.services.legal import (
    LegalService,
    client_ip_from_request,
    legal_gate_required_codes,
    subject_from_request,
)


router = APIRouter(prefix="/legal", tags=["legal"])


def _subject_from_principal(principal: Principal) -> tuple[LegalSubjectType, str]:
    context = principal_context(principal)
    raw_claims = principal.raw_claims if isinstance(principal.raw_claims, dict) else {}

    def _fallback_user_subject() -> tuple[LegalSubjectType, str]:
        actor_id = context.get("actor_id") or raw_claims.get("user_id") or raw_claims.get("sub")
        if actor_id:
            return LegalSubjectType.USER, str(actor_id)
        if principal.user_id:
            return LegalSubjectType.USER, str(principal.user_id)
        raise HTTPException(status_code=403, detail="missing_subject")

    if context["actor_type"] == "client":
        if principal.client_id is None:
            return _fallback_user_subject()
        org_id = context.get("org_id")
        if org_id and str(org_id) != str(principal.client_id):
            raise HTTPException(status_code=403, detail="client_org_mismatch")
        return LegalSubjectType.CLIENT, str(principal.client_id)
    if context["actor_type"] == "partner":
        if principal.partner_id is None:
            return _fallback_user_subject()
        partner_id = context.get("partner_id") or context.get("org_id")
        if partner_id and str(partner_id) != str(principal.partner_id):
            raise HTTPException(status_code=403, detail="partner_mismatch")
        return LegalSubjectType.PARTNER, str(principal.partner_id)
    if context["actor_type"] == "admin":
        actor_id = context.get("actor_id")
        if not actor_id:
            return _fallback_user_subject()
        return LegalSubjectType.USER, str(actor_id)
    if principal.user_id:
        return LegalSubjectType.USER, str(principal.user_id)
    return _fallback_user_subject()


@router.get("/required", response_model=LegalRequiredResponse)
def get_required(
    principal: Principal = Depends(get_portal_principal),
    db: Session = Depends(get_db),
) -> LegalRequiredResponse:
    subject_type, subject_id = _subject_from_principal(principal)
    subject = subject_from_request(subject_type=subject_type, subject_id=subject_id)
    service = LegalService(db)
    required = service.required_documents(subject=subject, required_codes=legal_gate_required_codes())
    return LegalRequiredResponse(
        subject={"type": subject.subject_type.value, "id": subject.subject_id},
        required=required,
        is_blocked=any(not item["accepted"] for item in required),
    )


@router.get("/documents/{code}", response_model=LegalDocumentResponse)
def get_document(
    code: str,
    version: str | None = Query(None),
    locale: str | None = Query(None),
    principal: Principal = Depends(get_portal_principal),
    db: Session = Depends(get_db),
) -> LegalDocumentResponse:
    _subject_from_principal(principal)
    service = LegalService(db)
    document = service.resolve_document(code=code, version=version, locale=locale)
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


@router.post("/accept", response_model=LegalRequiredResponse)
def accept_document(
    payload: LegalAcceptRequest,
    request: Request,
    principal: Principal = Depends(get_portal_principal),
    db: Session = Depends(get_db),
) -> LegalRequiredResponse:
    if not payload.accepted:
        raise HTTPException(status_code=400, detail="legal_acceptance_required")
    subject_type, subject_id = _subject_from_principal(principal)
    subject = subject_from_request(subject_type=subject_type, subject_id=subject_id)

    service = LegalService(db)
    document = service.resolve_document(code=payload.code, version=payload.version, locale=payload.locale)
    if document.status != LegalDocumentStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="legal_document_not_published")
    if document.effective_from > datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="legal_document_not_effective")

    request_ctx = request_context_from_request(request, token=principal.raw_claims)
    ip = client_ip_from_request(request)
    user_agent = request.headers.get("user-agent")
    service.accept_document(
        subject=subject,
        document=document,
        ip=ip,
        user_agent=user_agent,
        signature=payload.signature,
        meta=payload.meta,
        request_ctx=request_ctx,
    )
    db.commit()

    required = service.required_documents(subject=subject, required_codes=legal_gate_required_codes())
    return LegalRequiredResponse(
        subject={"type": subject.subject_type.value, "id": subject.subject_id},
        required=required,
        is_blocked=any(not item["accepted"] for item in required),
    )


__all__ = ["router"]

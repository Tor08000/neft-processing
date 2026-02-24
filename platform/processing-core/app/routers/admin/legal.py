from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.legal_acceptance import LegalAcceptance, LegalSubjectType
from app.models.legal_document import LegalDocument, LegalDocumentStatus
from app.models.partner import Partner
from app.models.partner_legal import PartnerLegalProfile, PartnerLegalStatus
from app.schemas.admin.legal_partners import (
    LegalPartnerDetail,
    LegalPartnerListResponse,
    LegalPartnerStatusUpdate,
    LegalPartnerSummary,
)
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
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService


router = APIRouter(prefix="/legal", tags=["admin-legal"])


_ALLOWED_LEGAL_ROLES = {"SUPERADMIN", "PLATFORM_ADMIN", "LEGAL_ADMIN", "ADMIN"}


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


@router.get("/partners-legacy", response_model=LegalPartnerListResponse)
def list_legal_partners(
    status: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalPartnerListResponse:
    _ensure_legal_admin(token)
    query = db.query(Partner, PartnerLegalProfile).outerjoin(
        PartnerLegalProfile, PartnerLegalProfile.partner_id == Partner.id
    )
    if status:
        try:
            status_enum = PartnerLegalStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_status") from exc
        query = query.filter(PartnerLegalProfile.legal_status == status_enum)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Partner.id.ilike(like), Partner.name.ilike(like)))
    total = query.count()
    rows = query.order_by(Partner.created_at.desc()).offset(offset).limit(limit).all()
    items: list[LegalPartnerSummary] = []
    for partner, profile in rows:
        legal_status = None
        updated_at = partner.created_at
        payout_blocked = None
        if profile:
            legal_status = profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status)
            updated_at = profile.updated_at or updated_at
            payout_blocked = legal_status != PartnerLegalStatus.VERIFIED.value
        items.append(
            LegalPartnerSummary(
                partner_id=str(partner.id),
                partner_name=partner.name,
                legal_status=legal_status,
                payout_blocked=payout_blocked,
                updated_at=updated_at,
            )
        )
    return LegalPartnerListResponse(items=items, total=total, limit=limit, offset=offset, cursor=None)


@router.get("/partners-legacy/{partner_id}", response_model=LegalPartnerDetail)
def get_legal_partner(
    partner_id: str,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalPartnerDetail:
    _ensure_legal_admin(token)
    partner = db.query(Partner).filter(Partner.id == partner_id).one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="partner_not_found")
    service = PartnerLegalService(db, request_ctx=request_context_from_request(None, token=token))
    profile = service.get_profile(partner_id=partner_id)
    details = service.get_details(partner_id=partner_id)
    tax_context = service.build_tax_context(profile=profile)
    legal_status = profile.legal_status.value if profile and hasattr(profile.legal_status, "value") else (
        str(profile.legal_status) if profile else None
    )
    payout_blocks: list[str] = []
    if legal_status and legal_status != PartnerLegalStatus.VERIFIED.value:
        payout_blocks.append("legal_status_not_verified")
    profile_payload = None
    if profile or details:
        profile_payload = {
            "legal_type": profile.legal_type.value if profile and hasattr(profile.legal_type, "value") else None,
            "country": profile.country if profile else None,
            "tax_residency": profile.tax_residency if profile else None,
            "tax_regime": profile.tax_regime.value if profile and profile.tax_regime else None,
            "vat_applicable": bool(profile.vat_applicable) if profile else None,
            "vat_rate": float(profile.vat_rate) if profile and profile.vat_rate is not None else None,
            "legal_status": legal_status,
            "details": {
                "legal_name": details.legal_name,
                "inn": details.inn,
                "kpp": details.kpp,
                "ogrn": details.ogrn,
                "passport": details.passport,
                "bank_account": details.bank_account,
                "bank_bic": details.bank_bic,
                "bank_name": details.bank_name,
                "created_at": details.created_at,
                "updated_at": details.updated_at,
            }
            if details
            else None,
            "tax_context": tax_context.to_dict() if tax_context else None,
            "created_at": profile.created_at if profile else None,
            "updated_at": profile.updated_at if profile else None,
        }
    return LegalPartnerDetail(
        partner_id=str(partner.id),
        partner_name=partner.name,
        legal_status=legal_status,
        payout_blocks=payout_blocks,
        documents=[],
        profile=profile_payload,
        raw=None,
    )


@router.post("/partners-legacy/{partner_id}/status", response_model=LegalPartnerDetail)
def update_legal_partner_status(
    partner_id: str,
    payload: LegalPartnerStatusUpdate,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LegalPartnerDetail:
    _ensure_legal_admin(token)
    service = PartnerLegalService(db, request_ctx=request_context_from_request(request, token=token))
    try:
        status_enum = PartnerLegalStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_status") from exc
    try:
        service.update_status(
            partner_id=partner_id,
            status=status_enum,
            comment=payload.reason,
        )
    except PartnerLegalError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    db.commit()
    return get_legal_partner(partner_id=partner_id, token=token, db=db)


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

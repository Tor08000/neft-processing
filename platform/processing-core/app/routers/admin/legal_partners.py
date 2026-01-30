from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.partner import Partner
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalPack, PartnerLegalProfile, PartnerLegalStatus
from app.schemas.admin.legal_partners import (
    LegalPartnerDetail,
    LegalPartnerDocument,
    LegalPartnerListResponse,
    LegalPartnerStatusUpdate,
    LegalPartnerSummary,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService

router = APIRouter(prefix="/legal", tags=["admin-legal-partners"])


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return all(inspector.has_table(name) for name in table_names)
    except Exception:
        return False


def _serialize_summary(
    partner: Partner,
    profile: PartnerLegalProfile | None,
    details: PartnerLegalDetails | None,
) -> LegalPartnerSummary:
    legal_status = profile.legal_status.value if profile and hasattr(profile.legal_status, "value") else None
    payout_blocked = None
    if profile is not None:
        payout_blocked = profile.legal_status == PartnerLegalStatus.BLOCKED
    updated_at = None
    if profile and profile.updated_at:
        updated_at = profile.updated_at
    elif details and details.updated_at:
        updated_at = details.updated_at
    else:
        updated_at = partner.created_at
    partner_name = partner.name or (details.legal_name if details else None)
    return LegalPartnerSummary(
        partner_id=str(partner.id),
        partner_name=partner_name,
        legal_status=legal_status,
        payout_blocked=payout_blocked,
        updated_at=updated_at,
    )


def _serialize_detail(
    partner: Partner,
    profile: PartnerLegalProfile | None,
    details: PartnerLegalDetails | None,
    documents: list[LegalPartnerDocument],
) -> LegalPartnerDetail:
    legal_status = profile.legal_status.value if profile and hasattr(profile.legal_status, "value") else None
    partner_name = partner.name or (details.legal_name if details else None)
    profile_payload: dict | None = None
    if profile or details:
        profile_payload = {
            "partner_id": str(partner.id),
            "legal_type": profile.legal_type.value if profile and profile.legal_type else None,
            "country": profile.country if profile else None,
            "tax_residency": profile.tax_residency if profile else None,
            "tax_regime": profile.tax_regime.value if profile and profile.tax_regime else None,
            "vat_applicable": bool(profile.vat_applicable) if profile and profile.vat_applicable is not None else None,
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
            "created_at": profile.created_at if profile else None,
            "updated_at": profile.updated_at if profile else None,
        }
    return LegalPartnerDetail(
        partner_id=str(partner.id),
        partner_name=partner_name,
        legal_status=legal_status,
        payout_blocks=None,
        documents=documents,
        profile=profile_payload,
        raw=None,
    )


@router.get("/partners", response_model=LegalPartnerListResponse)
def list_legal_partners(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> LegalPartnerListResponse:
    if not _tables_ready(db, ["partners"]):
        return LegalPartnerListResponse(items=[], total=0, cursor=None)

    has_profiles = _tables_ready(db, ["partner_legal_profiles"])
    has_details = _tables_ready(db, ["partner_legal_details"])

    query = db.query(Partner)
    if has_profiles:
        query = query.outerjoin(PartnerLegalProfile, PartnerLegalProfile.partner_id == Partner.id).add_entity(
            PartnerLegalProfile
        )
    if has_details:
        query = query.outerjoin(PartnerLegalDetails, PartnerLegalDetails.partner_id == Partner.id).add_entity(
            PartnerLegalDetails
        )

    if status:
        if not has_profiles:
            return LegalPartnerListResponse(items=[], total=0, cursor=None)
        try:
            status_value = PartnerLegalStatus(status)
        except ValueError:
            return LegalPartnerListResponse(items=[], total=0, cursor=None)
        query = query.filter(PartnerLegalProfile.legal_status == status_value)

    if search:
        search_like = f"%{search}%"
        if has_details:
            query = query.filter(
                or_(
                    Partner.id.ilike(search_like),
                    Partner.name.ilike(search_like),
                    PartnerLegalDetails.legal_name.ilike(search_like),
                )
            )
        else:
            query = query.filter(or_(Partner.id.ilike(search_like), Partner.name.ilike(search_like)))

    total = query.count()
    rows = query.order_by(Partner.name.asc()).offset(offset).limit(limit).all()

    items: list[LegalPartnerSummary] = []
    for row in rows:
        if isinstance(row, tuple):
            partner = row[0]
            profile = row[1] if has_profiles else None
            details = row[2] if has_details else None
        else:
            partner = row
            profile = None
            details = None
        items.append(_serialize_summary(partner, profile, details))

    return LegalPartnerListResponse(items=items, total=total, cursor=None)


@router.get("/partners/{partner_id}", response_model=LegalPartnerDetail)
def get_legal_partner(
    partner_id: str,
    db: Session = Depends(get_db),
) -> LegalPartnerDetail:
    if not _tables_ready(db, ["partners"]):
        raise HTTPException(status_code=404, detail="partner_not_found")

    partner = db.query(Partner).filter(Partner.id == partner_id).one_or_none()
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_found")

    profile = None
    details = None
    documents: list[LegalPartnerDocument] = []
    if _tables_ready(db, ["partner_legal_profiles"]):
        profile = db.query(PartnerLegalProfile).filter(PartnerLegalProfile.partner_id == partner_id).one_or_none()
    if _tables_ready(db, ["partner_legal_details"]):
        details = db.query(PartnerLegalDetails).filter(PartnerLegalDetails.partner_id == partner_id).one_or_none()
    if _tables_ready(db, ["partner_legal_packs"]):
        packs = (
            db.query(PartnerLegalPack)
            .filter(PartnerLegalPack.partner_id == partner_id)
            .order_by(PartnerLegalPack.created_at.desc())
            .limit(20)
            .all()
        )
        documents = [
            LegalPartnerDocument(
                id=str(pack.id),
                title=pack.format,
                status=None,
                url=None,
                updated_at=pack.created_at,
            )
            for pack in packs
        ]

    return _serialize_detail(partner, profile, details, documents)


@router.post("/partners/{partner_id}/status", response_model=LegalPartnerDetail)
def update_legal_partner_status(
    partner_id: str,
    payload: LegalPartnerStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> LegalPartnerDetail:
    service = PartnerLegalService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        status = PartnerLegalStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_status") from exc
    try:
        service.update_status(partner_id=partner_id, status=status, comment=payload.reason)
    except PartnerLegalError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    db.commit()

    partner = db.query(Partner).filter(Partner.id == partner_id).one_or_none()
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_found")
    profile = db.query(PartnerLegalProfile).filter(PartnerLegalProfile.partner_id == partner_id).one_or_none()
    details = None
    if _tables_ready(db, ["partner_legal_details"]):
        details = db.query(PartnerLegalDetails).filter(PartnerLegalDetails.partner_id == partner_id).one_or_none()
    return _serialize_detail(partner, profile, details, documents=[])


__all__ = ["router"]

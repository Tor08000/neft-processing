from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.partner_legal import (
    PartnerLegalChecklistOut,
    PartnerLegalDetailsIn,
    PartnerLegalDetailsOut,
    PartnerLegalProfileIn,
    PartnerLegalProfileOut,
    PartnerLegalProfileResponse,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import request_context_from_request
from app.models.partner_legal import PartnerLegalStatus, PartnerLegalType, PartnerTaxRegime
from app.services.partner_legal_service import PartnerLegalService

router = APIRouter(prefix="/partner/legal", tags=["partner-legal"])


def _resolve_partner_id(principal: Principal) -> str:
    raw = principal.raw_claims.get("org_id") or principal.raw_claims.get("partner_id")
    if raw is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_org_context"})
    return str(raw)


def _details_out(details) -> PartnerLegalDetailsOut | None:
    if details is None:
        return None
    return PartnerLegalDetailsOut(
        partner_id=str(details.partner_id),
        legal_name=details.legal_name,
        inn=details.inn,
        kpp=details.kpp,
        ogrn=details.ogrn,
        passport=details.passport,
        bank_account=details.bank_account,
        bank_bic=details.bank_bic,
        bank_name=details.bank_name,
        created_at=details.created_at,
        updated_at=details.updated_at,
    )


def _profile_out(profile, details, tax_context) -> PartnerLegalProfileOut | None:
    if profile is None:
        return None
    return PartnerLegalProfileOut(
        partner_id=str(profile.partner_id),
        legal_type=profile.legal_type.value if hasattr(profile.legal_type, "value") else str(profile.legal_type),
        country=profile.country,
        tax_residency=profile.tax_residency,
        tax_regime=profile.tax_regime.value if hasattr(profile.tax_regime, "value") else (profile.tax_regime or None),
        vat_applicable=bool(profile.vat_applicable),
        vat_rate=float(profile.vat_rate) if profile.vat_rate is not None else None,
        legal_status=profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status),
        details=_details_out(details),
        tax_context=tax_context,
    )


@router.get("/profile", response_model=PartnerLegalProfileResponse)
def get_partner_legal_profile(
    principal: Principal = Depends(require_permission("partner:profile:view")),
    db: Session = Depends(get_db),
) -> PartnerLegalProfileResponse:
    partner_id = _resolve_partner_id(principal)
    service = PartnerLegalService(db)
    profile = service.get_profile(partner_id=partner_id)
    details = service.get_details(partner_id=partner_id)
    tax_context = service.build_tax_context(profile=profile)
    checklist = PartnerLegalChecklistOut(
        legal_profile=profile is not None,
        legal_details=details is not None,
        verified=bool(profile and profile.legal_status == PartnerLegalStatus.VERIFIED),
    )
    return PartnerLegalProfileResponse(
        profile=_profile_out(profile, details, tax_context.to_dict() if tax_context else None),
        checklist=checklist,
    )


@router.put("/profile", response_model=PartnerLegalProfileOut)
def upsert_partner_legal_profile(
    payload: PartnerLegalProfileIn,
    principal: Principal = Depends(require_permission("partner:profile:manage")),
    db: Session = Depends(get_db),
) -> PartnerLegalProfileOut:
    partner_id = _resolve_partner_id(principal)
    service = PartnerLegalService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    try:
        profile = service.upsert_profile(
            partner_id=partner_id,
            legal_type=PartnerLegalType(payload.legal_type),
            country=payload.country,
            tax_residency=payload.tax_residency,
            tax_regime=PartnerTaxRegime(payload.tax_regime) if payload.tax_regime else None,
            vat_applicable=payload.vat_applicable,
            vat_rate=payload.vat_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_legal_profile_payload") from exc
    db.commit()
    details = service.get_details(partner_id=partner_id)
    tax_context = service.build_tax_context(profile=profile)
    return _profile_out(profile, details, tax_context.to_dict() if tax_context else None)


@router.put("/details", response_model=PartnerLegalDetailsOut)
def upsert_partner_legal_details(
    payload: PartnerLegalDetailsIn,
    principal: Principal = Depends(require_permission("partner:profile:manage")),
    db: Session = Depends(get_db),
) -> PartnerLegalDetailsOut:
    partner_id = _resolve_partner_id(principal)
    service = PartnerLegalService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    details = service.upsert_details(
        partner_id=partner_id,
        legal_name=payload.legal_name,
        inn=payload.inn,
        kpp=payload.kpp,
        ogrn=payload.ogrn,
        passport=payload.passport,
        bank_account=payload.bank_account,
        bank_bic=payload.bank_bic,
        bank_name=payload.bank_name,
    )
    db.commit()
    return _details_out(details)

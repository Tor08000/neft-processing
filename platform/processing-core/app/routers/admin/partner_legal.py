from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.admin.partner_legal import (
    PartnerLegalPackHistoryResponse,
    PartnerLegalPackOut,
    PartnerLegalPackRequest,
    PartnerLegalProfileAdminOut,
    PartnerLegalProfileStatusUpdate,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.partner_legal_pack_service import PartnerLegalPackService
from app.models.partner_legal import PartnerLegalStatus
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService

router = APIRouter(prefix="/partners", tags=["admin-partner-legal"])


def _details_payload(details) -> dict | None:
    if details is None:
        return None
    return {
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


def _pack_out(pack, download_url: str | None = None) -> PartnerLegalPackOut:
    return PartnerLegalPackOut(
        id=str(pack.id),
        partner_id=str(pack.partner_id),
        format=pack.format,
        object_key=pack.object_key,
        pack_hash=pack.pack_hash,
        metadata=pack.metadata_json,
        created_at=pack.created_at,
        download_url=download_url,
    )


@router.get("/{partner_id}/legal-profile", response_model=PartnerLegalProfileAdminOut)
def get_partner_legal_profile(
    partner_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerLegalProfileAdminOut:
    service = PartnerLegalService(db, request_ctx=request_context_from_request(None, token=_sanitize_token_for_audit(token)))
    profile = service.get_profile(partner_id=partner_id)
    details = service.get_details(partner_id=partner_id)
    tax_context = service.build_tax_context(profile=profile)
    if profile is None:
        return PartnerLegalProfileAdminOut(
            partner_id=partner_id,
            details=_details_payload(details),
            tax_context=tax_context.to_dict() if tax_context else None,
        )
    return PartnerLegalProfileAdminOut(
        partner_id=partner_id,
        legal_type=profile.legal_type.value if hasattr(profile.legal_type, "value") else str(profile.legal_type),
        country=profile.country,
        tax_residency=profile.tax_residency,
        tax_regime=profile.tax_regime.value if profile.tax_regime else None,
        vat_applicable=bool(profile.vat_applicable),
        vat_rate=float(profile.vat_rate) if profile.vat_rate is not None else None,
        legal_status=profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status),
        details=_details_payload(details),
        tax_context=tax_context.to_dict() if tax_context else None,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post("/{partner_id}/legal-profile/status", response_model=PartnerLegalProfileAdminOut)
def update_partner_legal_status(
    partner_id: str,
    payload: PartnerLegalProfileStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerLegalProfileAdminOut:
    service = PartnerLegalService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        profile = service.update_status(
            partner_id=partner_id,
            status=PartnerLegalStatus(payload.status),
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_status") from exc
    except PartnerLegalError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    db.commit()
    details = service.get_details(partner_id=partner_id)
    tax_context = service.build_tax_context(profile=profile)
    return PartnerLegalProfileAdminOut(
        partner_id=partner_id,
        legal_type=profile.legal_type.value if hasattr(profile.legal_type, "value") else str(profile.legal_type),
        country=profile.country,
        tax_residency=profile.tax_residency,
        tax_regime=profile.tax_regime.value if profile.tax_regime else None,
        vat_applicable=bool(profile.vat_applicable),
        vat_rate=float(profile.vat_rate) if profile.vat_rate is not None else None,
        legal_status=profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status),
        details=_details_payload(details),
        tax_context=tax_context.to_dict() if tax_context else None,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post("/{partner_id}/legal-pack", response_model=PartnerLegalPackOut)
def generate_partner_legal_pack(
    partner_id: str,
    payload: PartnerLegalPackRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerLegalPackOut:
    _ = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    service = PartnerLegalPackService(db)
    result = service.generate_pack(partner_id=partner_id, format=payload.format)
    db.commit()
    return PartnerLegalPackOut(
        id=result.pack_id,
        partner_id=result.partner_id,
        format=result.format,
        object_key=result.object_key,
        pack_hash=result.pack_hash,
        metadata=result.metadata,
        created_at=datetime.now(timezone.utc),
        download_url=result.download_url,
    )


@router.get("/{partner_id}/legal-pack/history", response_model=PartnerLegalPackHistoryResponse)
def list_partner_legal_packs(
    partner_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerLegalPackHistoryResponse:
    _ = token
    service = PartnerLegalPackService(db)
    items = service.list_history(partner_id=partner_id)
    return PartnerLegalPackHistoryResponse(items=[_pack_out(item) for item in items])

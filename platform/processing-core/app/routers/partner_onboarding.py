from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.legal_acceptance import LegalSubjectType
from app.models.partner import Partner
from app.models.partner_legal import PartnerLegalStatus
from app.models.partner_management import PartnerUserRole
from app.schemas.partner_onboarding import (
    PartnerOnboardingChecklistOut,
    PartnerOnboardingPartnerOut,
    PartnerOnboardingProfilePatch,
    PartnerOnboardingSnapshotOut,
)
from app.services.audit_service import (
    AuditService,
    AuditVisibility,
    _sanitize_token_for_audit,
    request_context_from_request,
)
from app.services.partner_context import (
    resolve_partner_from_link,
    resolve_partner_user_link,
    update_partner_runtime_fields,
)
from app.services.legal import LegalService, legal_gate_required_codes, subject_from_request
from app.services.partner_auth import require_partner_user
from app.services.partner_legal_service import PartnerLegalService


router = APIRouter(prefix="/partner/onboarding", tags=["partner-onboarding"])

PROFILE_MANAGER_ROLES = {
    "PARTNER_OWNER",
    "PARTNER_MANAGER",
    "PARTNER_ACCOUNTANT",
    "PARTNER_SERVICE_MANAGER",
}


def _user_id_from_token(token: dict[str, Any]) -> str:
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user_context")
    return user_id


def _current_partner_link(
    token: dict[str, Any] = Depends(require_partner_user),
    db: Session = Depends(get_db),
) -> PartnerUserRole:
    _user_id_from_token(token)
    link = resolve_partner_user_link(db, claims=token)
    if not link:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    return link


def _current_partner(
    link: PartnerUserRole = Depends(_current_partner_link),
    db: Session = Depends(get_db),
) -> Partner:
    partner = resolve_partner_from_link(db, link=link)
    if not partner:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    return partner


def _ensure_any_role(link: PartnerUserRole, allowed_roles: set[str]) -> None:
    roles = {str(role).upper() for role in (link.roles or []) if role}
    if roles.isdisjoint(allowed_roles):
        raise HTTPException(status_code=403, detail="forbidden")


def _has_contact_value(contacts: dict[str, Any] | None) -> bool:
    if not isinstance(contacts, dict) or not contacts:
        return False
    for value in contacts.values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (int, float)) and value:
            return True
        if isinstance(value, dict) and _has_contact_value(value):
            return True
        if isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value):
            return True
    return False


def _profile_complete(partner: Partner) -> bool:
    return bool((partner.brand_name or "").strip()) and _has_contact_value(partner.contacts)


def _profile_complete_payload(*, brand_name: str | None, contacts: dict[str, Any] | None) -> bool:
    return bool((brand_name or "").strip()) and _has_contact_value(contacts)


def _legal_documents_accepted(db: Session, *, subject_id: str) -> bool:
    required_codes = legal_gate_required_codes()
    if not required_codes:
        return True
    service = LegalService(db)
    subject = subject_from_request(subject_type=LegalSubjectType.PARTNER, subject_id=subject_id)
    required = service.required_documents(subject=subject, required_codes=required_codes)
    return all(item["accepted"] for item in required)


def _blocked_reasons(
    *,
    profile_complete: bool,
    legal_documents_accepted: bool,
    legal_profile_present: bool,
    legal_details_present: bool,
    legal_details_complete: bool,
    legal_status: PartnerLegalStatus | None,
) -> list[str]:
    reasons: list[str] = []
    if not profile_complete:
        reasons.append("profile_incomplete")
    if not legal_documents_accepted:
        reasons.append("legal_documents_pending")
    if not legal_profile_present:
        reasons.append("legal_profile_missing")
    if not legal_details_present:
        reasons.append("legal_details_missing")
    elif not legal_details_complete:
        reasons.append("legal_details_incomplete")

    if legal_status == PartnerLegalStatus.BLOCKED:
        reasons.append("legal_review_blocked")
    elif legal_status != PartnerLegalStatus.VERIFIED:
        reasons.append("legal_review_pending")
    return reasons


def _next_step(blocked_reasons: list[str]) -> tuple[str, str]:
    if any(reason.startswith("profile_") for reason in blocked_reasons):
        return "profile", "/onboarding"
    if any(reason.startswith("legal_documents_") for reason in blocked_reasons):
        return "legal_documents", "/legal"
    if any(reason.startswith("legal_profile") or reason.startswith("legal_details") for reason in blocked_reasons):
        return "legal_profile", "/onboarding"
    if any(reason.startswith("legal_review") for reason in blocked_reasons):
        return "legal_review", "/onboarding"
    return "activate", "/onboarding"


def _partner_scope_id(token: dict[str, Any], partner: Partner) -> str:
    return str(partner.id)


def _snapshot(
    db: Session,
    *,
    partner: Partner,
    token: dict[str, Any],
) -> PartnerOnboardingSnapshotOut:
    partner_scope_id = _partner_scope_id(token, partner)
    profile_complete = _profile_complete(partner)
    legal_service = PartnerLegalService(db)
    legal_profile = legal_service.get_profile(partner_id=partner_scope_id)
    legal_details = legal_service.get_details(partner_id=partner_scope_id)
    legal_profile_present = legal_profile is not None
    legal_details_present = legal_details is not None
    legal_details_complete = legal_service.is_details_complete(profile=legal_profile, details=legal_details)
    legal_documents_accepted = _legal_documents_accepted(db, subject_id=partner_scope_id)
    legal_verified = legal_profile is not None and legal_profile.legal_status == PartnerLegalStatus.VERIFIED
    blocked_reasons = _blocked_reasons(
        profile_complete=profile_complete,
        legal_documents_accepted=legal_documents_accepted,
        legal_profile_present=legal_profile_present,
        legal_details_present=legal_details_present,
        legal_details_complete=legal_details_complete,
        legal_status=legal_profile.legal_status if legal_profile else None,
    )
    activation_ready = not blocked_reasons
    next_step, next_route = _next_step(blocked_reasons)
    return PartnerOnboardingSnapshotOut(
        partner=PartnerOnboardingPartnerOut(
            id=str(partner.id),
            code=partner.code,
            legal_name=partner.legal_name,
            brand_name=partner.brand_name,
            partner_type=partner.partner_type,
            status=str(partner.status),
            contacts=partner.contacts or {},
        ),
        checklist=PartnerOnboardingChecklistOut(
            profile_complete=profile_complete,
            legal_documents_accepted=legal_documents_accepted,
            legal_profile_present=legal_profile_present,
            legal_details_present=legal_details_present,
            legal_details_complete=legal_details_complete,
            legal_verified=legal_verified,
            activation_ready=activation_ready,
            blocked_reasons=blocked_reasons,
            next_step=next_step,
            next_route=next_route,
        ),
    )


@router.get("", response_model=PartnerOnboardingSnapshotOut)
def get_partner_onboarding(
    token: dict[str, Any] = Depends(require_partner_user),
    partner: Partner = Depends(_current_partner),
    db: Session = Depends(get_db),
) -> PartnerOnboardingSnapshotOut:
    return _snapshot(db, partner=partner, token=token)


@router.patch("/profile", response_model=PartnerOnboardingPartnerOut)
def patch_partner_onboarding_profile(
    payload: PartnerOnboardingProfilePatch,
    request: Request,
    token: dict[str, Any] = Depends(require_partner_user),
    partner: Partner = Depends(_current_partner),
    link: PartnerUserRole = Depends(_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerOnboardingPartnerOut:
    _ensure_any_role(link, PROFILE_MANAGER_ROLES)
    before = {
        "brand_name": partner.brand_name,
        "contacts": partner.contacts or {},
        "status": partner.status,
    }
    next_contacts = payload.contacts if payload.contacts is not None else (partner.contacts or {})
    next_brand_name = payload.brand_name if payload.brand_name is not None else partner.brand_name
    after = {
        "brand_name": next_brand_name,
        "contacts": next_contacts,
        "status": partner.status,
    }

    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    if not _profile_complete_payload(
        brand_name=before["brand_name"],
        contacts=before["contacts"],
    ) and _profile_complete_payload(brand_name=next_brand_name, contacts=next_contacts):
        AuditService(db).audit(
            event_type="PARTNER_ONBOARDING_STARTED",
            entity_type="partner",
            entity_id=str(partner.id),
            action="partner_onboarding_started",
            visibility=AuditVisibility.INTERNAL,
            before=before,
            after=after,
            request_ctx=request_ctx,
        )
    AuditService(db).audit(
        event_type="PARTNER_ONBOARDING_PROFILE_UPDATED",
        entity_type="partner",
        entity_id=str(partner.id),
        action="partner_onboarding_profile_updated",
        visibility=AuditVisibility.INTERNAL,
        before=before,
        after=after,
        request_ctx=request_ctx,
    )
    partner = update_partner_runtime_fields(
        db,
        partner_id=str(partner.id),
        brand_name=next_brand_name,
        contacts=next_contacts,
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_linked")
    return PartnerOnboardingPartnerOut(
        id=str(partner.id),
        code=partner.code,
        legal_name=partner.legal_name,
        brand_name=partner.brand_name,
        partner_type=partner.partner_type,
        status=str(partner.status),
        contacts=partner.contacts or {},
    )


@router.post("/activate", response_model=PartnerOnboardingSnapshotOut)
def activate_partner_onboarding(
    request: Request,
    token: dict[str, Any] = Depends(require_partner_user),
    partner: Partner = Depends(_current_partner),
    link: PartnerUserRole = Depends(_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerOnboardingSnapshotOut:
    _ensure_any_role(link, PROFILE_MANAGER_ROLES)
    snapshot = _snapshot(db, partner=partner, token=token)
    if not snapshot.checklist.activation_ready:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "partner_onboarding_incomplete",
                "blocked_reasons": snapshot.checklist.blocked_reasons,
            },
        )

    before = {
        "status": partner.status,
        "brand_name": partner.brand_name,
        "contacts": partner.contacts or {},
    }
    after = {
        "status": "ACTIVE",
        "brand_name": partner.brand_name,
        "contacts": partner.contacts or {},
    }
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    AuditService(db).audit(
        event_type="PARTNER_ACTIVATED",
        entity_type="partner",
        entity_id=str(partner.id),
        action="partner_activated",
        visibility=AuditVisibility.INTERNAL,
        before=before,
        after=after,
        request_ctx=request_ctx,
    )
    partner = update_partner_runtime_fields(
        db,
        partner_id=str(partner.id),
        status="ACTIVE",
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_linked")
    return _snapshot(db, partner=partner, token=token)


__all__ = ["router"]

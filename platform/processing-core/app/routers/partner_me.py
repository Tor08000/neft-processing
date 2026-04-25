from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.portal import portal_user
from app.db import get_db
from app.schemas.partner_me import PartnerMeOrg, PartnerMeResponse, PartnerMeUser
from app.services.portal_me import build_portal_me

# Compatibility projection over the canonical portal bootstrap source; reduced payload, not SSoT.
router = APIRouter(prefix="/partner", tags=["partner-me"])


@router.get("/me", response_model=PartnerMeResponse)
def get_partner_me(
    token: dict = Depends(portal_user),
    db: Session = Depends(get_db),
) -> PartnerMeResponse:
    portal = build_portal_me(db, token=token)
    return PartnerMeResponse(
        user=PartnerMeUser(
            id=portal.user.id,
            email=portal.user.email,
            subject_type=portal.user.subject_type,
        ),
        org=PartnerMeOrg(
            id=portal.org.id,
            name=portal.org.name,
            status=portal.org.status,
        )
        if portal.org
        else None,
        org_roles=portal.org_roles,
        user_roles=portal.user_roles,
        entitlements_snapshot=portal.entitlements_snapshot,
        capabilities=portal.capabilities,
    )

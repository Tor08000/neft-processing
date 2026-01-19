from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.partner_core import PartnerProfile, PartnerProfileStatus


def ensure_partner_profile(
    db: Session,
    *,
    org_id: int,
    display_name: str | None = None,
) -> PartnerProfile:
    profile = db.query(PartnerProfile).filter(PartnerProfile.org_id == org_id).one_or_none()
    if profile:
        return profile
    profile = PartnerProfile(
        org_id=org_id,
        status=PartnerProfileStatus.ONBOARDING,
        display_name=display_name,
    )
    db.add(profile)
    db.flush()
    return profile


def profile_payload(profile: PartnerProfile) -> dict:
    return {
        "id": str(profile.id),
        "org_id": profile.org_id,
        "status": profile.status.value if hasattr(profile.status, "value") else str(profile.status),
        "display_name": profile.display_name,
        "contacts_json": profile.contacts_json,
        "meta_json": profile.meta_json,
        "created_at": profile.created_at or datetime.now(timezone.utc),
        "updated_at": profile.updated_at or datetime.now(timezone.utc),
    }


__all__ = ["ensure_partner_profile", "profile_payload"]

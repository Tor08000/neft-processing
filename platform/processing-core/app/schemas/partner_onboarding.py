from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PartnerOnboardingPartnerOut(BaseModel):
    id: str
    code: str
    legal_name: str
    brand_name: str | None = None
    partner_type: str
    status: str
    contacts: dict[str, Any] = Field(default_factory=dict)


class PartnerOnboardingChecklistOut(BaseModel):
    profile_complete: bool
    legal_documents_accepted: bool
    legal_profile_present: bool
    legal_details_present: bool
    legal_details_complete: bool
    legal_verified: bool
    activation_ready: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    next_step: str
    next_route: str


class PartnerOnboardingSnapshotOut(BaseModel):
    partner: PartnerOnboardingPartnerOut
    checklist: PartnerOnboardingChecklistOut


class PartnerOnboardingProfilePatch(BaseModel):
    brand_name: str | None = None
    contacts: dict[str, Any] | None = None


__all__ = [
    "PartnerOnboardingChecklistOut",
    "PartnerOnboardingPartnerOut",
    "PartnerOnboardingProfilePatch",
    "PartnerOnboardingSnapshotOut",
]

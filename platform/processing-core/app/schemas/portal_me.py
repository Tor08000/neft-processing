from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PortalMeUser(BaseModel):
    id: str
    email: str | None = None
    subject_type: str | None = None
    timezone: str | None = None


class PortalMeOrg(BaseModel):
    id: str
    name: str | None = None
    inn: str | None = None
    status: str | None = None
    timezone: str | None = None


class PortalMeSubscription(BaseModel):
    plan_code: str | None = None
    status: str | None = None
    billing_cycle: str | None = None
    support_plan: str | None = None
    slo_tier: str | None = None
    addons: list[dict[str, Any]] | None = None


class PortalNavSection(BaseModel):
    code: str
    label: str


class PortalMePartnerProfile(BaseModel):
    display_name: str | None = None
    contacts_json: dict[str, Any] | None = None
    meta_json: dict[str, Any] | None = None


class PortalMePartner(BaseModel):
    status: str | None = None
    profile: PortalMePartnerProfile | None = None


class PortalMeResponse(BaseModel):
    user: PortalMeUser
    org: PortalMeOrg | None = None
    org_roles: list[str]
    user_roles: list[str]
    subscription: PortalMeSubscription | None = None
    entitlements_snapshot: dict[str, Any] | None = None
    capabilities: list[str]
    nav_sections: list[PortalNavSection] | None = None
    partner: PortalMePartner | None = None

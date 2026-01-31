from __future__ import annotations

from typing import Any

from app.schemas.portal_me import PortalAccessState, PortalMeLegal, PortalMePartner, PortalMeSubscription

OVERDUE_STATUSES = {"OVERDUE", "PAST_DUE", "PASTDUE", "DELINQUENT"}
SUSPENDED_STATUSES = {"SUSPENDED", "BLOCKED", "PAUSED"}


def _normalize_status(value: str | None) -> str | None:
    return str(value).upper() if value else None


def resolve_access_state(
    *,
    actor_type: str,
    org_status: str | None,
    org_roles: list[str],
    subscription: PortalMeSubscription | None,
    legal: PortalMeLegal | None,
    partner: PortalMePartner | None,
    entitlements_snapshot: dict[str, Any] | None,
    capabilities: list[str],
    contract_status: str | None = None,
    onboarding_profile_complete: bool | None = None,
) -> tuple[PortalAccessState, str | None]:
    if actor_type == "admin":
        return PortalAccessState.ACTIVE, None

    upper_roles = {str(role).upper() for role in org_roles if role}
    subscription_status = _normalize_status(subscription.status) if subscription else None

    if "CLIENT" in upper_roles:
        if subscription_status and subscription_status in SUSPENDED_STATUSES:
            return PortalAccessState.SUSPENDED, "billing_suspended"
        if subscription_status and subscription_status in OVERDUE_STATUSES:
            return PortalAccessState.OVERDUE, "billing_overdue"

    if legal and legal.required_enabled and not legal.accepted:
        return PortalAccessState.LEGAL_PENDING, "legal_not_verified"

    if "CLIENT" in upper_roles:
        if onboarding_profile_complete is False:
            return PortalAccessState.NEEDS_ONBOARDING, "profile_missing"
        if not subscription or not subscription.plan_code:
            return PortalAccessState.NEEDS_PLAN, "subscription_missing"
        if not contract_status:
            return PortalAccessState.NEEDS_CONTRACT, "contract_missing"
        if _normalize_status(contract_status) not in {"SIGNED", "SIGNED_SIMPLE", "SIGNED_PEP"}:
            return PortalAccessState.NEEDS_CONTRACT, "contract_not_signed"
        normalized_org_status = _normalize_status(org_status)
        if not normalized_org_status or normalized_org_status not in {"ACTIVE", "ONBOARDING"}:
            return PortalAccessState.NEEDS_ONBOARDING, "org_not_active"
    else:
        normalized_org_status = _normalize_status(org_status)
        if not normalized_org_status or normalized_org_status not in {"ACTIVE", "ONBOARDING"}:
            return PortalAccessState.NEEDS_ONBOARDING, "org_not_active"

    if "PARTNER" in upper_roles:
        if partner and partner.status and _normalize_status(partner.status) != "ACTIVE":
            return PortalAccessState.NEEDS_ONBOARDING, "partner_onboarding"

    modules_payload = None
    if isinstance(entitlements_snapshot, dict):
        modules_payload = entitlements_snapshot.get("modules")

    if isinstance(modules_payload, dict) and modules_payload:
        enabled_modules = [payload for payload in modules_payload.values() if payload and payload.get("enabled")]
        if not enabled_modules:
            return PortalAccessState.MODULE_DISABLED, "module_disabled"

    if entitlements_snapshot is not None and isinstance(entitlements_snapshot, dict):
        caps_payload = entitlements_snapshot.get("capabilities")
        if isinstance(caps_payload, list) and not caps_payload and not capabilities:
            return PortalAccessState.MISSING_CAPABILITY, "missing_capability"

    return PortalAccessState.ACTIVE, None


__all__ = ["resolve_access_state"]

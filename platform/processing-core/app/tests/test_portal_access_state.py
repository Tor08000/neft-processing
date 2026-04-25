from __future__ import annotations

from app.schemas.portal_me import PortalMeLegal, PortalMePartner, PortalMeSubscription, PortalAccessState
from app.services.portal_access_state import resolve_access_state


def test_access_state_needs_onboarding_when_org_missing():
    state, reason = resolve_access_state(
        actor_type="client",
        org_status=None,
        org_roles=["CLIENT"],
        subscription=None,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=None,
        capabilities=[],
    )
    assert state == PortalAccessState.NEEDS_ONBOARDING
    assert reason == "org_pending"


def test_access_state_needs_plan_when_subscription_missing():
    state, reason = resolve_access_state(
        actor_type="client",
        org_status="ACTIVE",
        org_roles=["CLIENT"],
        subscription=None,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=None,
        capabilities=[],
    )
    assert state == PortalAccessState.NEEDS_PLAN
    assert reason == "subscription_missing"


def test_access_state_overdue():
    subscription = PortalMeSubscription(plan_code="PRO", status="OVERDUE")
    state, reason = resolve_access_state(
        actor_type="client",
        org_status="ACTIVE",
        org_roles=["CLIENT"],
        subscription=subscription,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=None,
        capabilities=[],
    )
    assert state == PortalAccessState.OVERDUE
    assert reason == "billing_overdue"


def test_access_state_suspended():
    subscription = PortalMeSubscription(plan_code="PRO", status="SUSPENDED")
    state, reason = resolve_access_state(
        actor_type="client",
        org_status="ACTIVE",
        org_roles=["CLIENT"],
        subscription=subscription,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=None,
        capabilities=[],
    )
    assert state == PortalAccessState.SUSPENDED
    assert reason == "billing_suspended"


def test_access_state_partner_legal_pending():
    legal = PortalMeLegal(required_count=1, accepted=False, missing=["DOC"], required_enabled=True)
    state, reason = resolve_access_state(
        actor_type="partner",
        org_status="ACTIVE",
        org_roles=["PARTNER"],
        subscription=None,
        legal=legal,
        partner=PortalMePartner(status="ACTIVE"),
        entitlements_snapshot=None,
        capabilities=[],
    )
    assert state == PortalAccessState.LEGAL_PENDING
    assert reason == "legal_not_verified"


def test_access_state_module_disabled():
    subscription = PortalMeSubscription(plan_code="PRO", status="ACTIVE")
    entitlements_snapshot = {"modules": {"CARDS": {"enabled": False}}}
    state, reason = resolve_access_state(
        actor_type="client",
        org_status="ACTIVE",
        org_roles=["CLIENT"],
        subscription=subscription,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=entitlements_snapshot,
        capabilities=[],
        contract_status="SIGNED",
    )
    assert state == PortalAccessState.MODULE_DISABLED
    assert reason == "module_disabled"


def test_access_state_priority_overdue_over_module_disabled():
    subscription = PortalMeSubscription(plan_code="PRO", status="OVERDUE")
    entitlements_snapshot = {"modules": {"CARDS": {"enabled": False}}}
    state, reason = resolve_access_state(
        actor_type="client",
        org_status="ACTIVE",
        org_roles=["CLIENT"],
        subscription=subscription,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=None,
        entitlements_snapshot=entitlements_snapshot,
        capabilities=[],
        contract_status="SIGNED",
    )
    assert state == PortalAccessState.OVERDUE
    assert reason == "billing_overdue"


def test_access_state_partner_ignores_client_contract_rules_for_mixed_memberships():
    state, reason = resolve_access_state(
        actor_type="partner",
        org_status="ACTIVE",
        org_roles=["CLIENT", "PARTNER"],
        subscription=PortalMeSubscription(plan_code="PRO", status="ACTIVE"),
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=PortalMePartner(status="PENDING"),
        entitlements_snapshot={"modules": {"SUPPORT": {"enabled": True}}},
        capabilities=["PARTNER_CORE"],
        contract_status=None,
    )
    assert state == PortalAccessState.NEEDS_ONBOARDING
    assert reason == "partner_onboarding"


def test_access_state_active_partner_does_not_require_entitlement_capabilities():
    state, reason = resolve_access_state(
        actor_type="partner",
        org_status="ACTIVE",
        org_roles=["PARTNER"],
        subscription=None,
        legal=PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=True),
        partner=PortalMePartner(status="ACTIVE"),
        entitlements_snapshot={"org_roles": [], "capabilities": [], "modules": {}},
        capabilities=[],
        contract_status=None,
    )
    assert state == PortalAccessState.ACTIVE
    assert reason is None

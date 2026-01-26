from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.crm import CRMClient
from app.models.partner import Partner
from app.models.fleet import ClientEmployee
from app.models.legal_acceptance import LegalSubjectType
from app.models.subscriptions_v1 import SubscriptionPlan
from app.schemas.portal_me import (
    PortalMeOrg,
    PortalMePartner,
    PortalMePartnerFinanceState,
    PortalMePartnerLegalState,
    PortalMePartnerProfile,
    PortalMeLegal,
    PortalMeFeatures,
    PortalMeGating,
    PortalMeResponse,
    PortalMeSubscription,
    PortalMeUser,
    PortalNavSection,
    PortalAccessState,
)
from app.models.partner_finance import PartnerLedgerEntry, PartnerLedgerEntryType
from app.models.partner_legal import PartnerLegalStatus
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.jwt_support import parse_scopes
from app.services.legal import LegalService, legal_gate_required_codes, subject_from_request
from app.config import settings
from app.services.partner_core_service import ensure_partner_profile
from app.services.partner_finance_service import PartnerFinanceService
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService
from app.services.portal_access_state import resolve_access_state
from app.services.subscription_service import DEFAULT_TENANT_ID, get_client_subscription


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    inspector = inspect(db.get_bind())
    return inspector.has_table(name, schema=DB_SCHEMA)


def _normalize_roles(token: dict) -> list[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    return sorted({str(role) for role in roles if role})


def _resolve_org_id(token: dict) -> str | None:
    return token.get("org_id") or token.get("client_id") or token.get("partner_id")


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _resolve_actor_type(token: dict, org_roles: list[str]) -> str:
    if token.get("client_id") or token.get("subject_type") == "client_user" or "CLIENT" in org_roles:
        return "client"
    if token.get("partner_id") or "PARTNER" in org_roles:
        return "partner"
    return "admin"


def _resolve_subject(token: dict) -> tuple[LegalSubjectType, str] | None:
    if token.get("client_id"):
        return LegalSubjectType.CLIENT, str(token["client_id"])
    if token.get("partner_id"):
        return LegalSubjectType.PARTNER, str(token["partner_id"])
    if token.get("user_id") or token.get("sub"):
        return LegalSubjectType.USER, str(token.get("user_id") or token.get("sub"))
    return None


def _resolve_legal_status(db: Session, token: dict) -> PortalMeLegal:
    required_codes = legal_gate_required_codes()
    required_enabled = bool(required_codes)
    if not settings.CORE_ONBOARDING_ENABLED:
        return PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=False)

    subject_info = _resolve_subject(token)
    if subject_info is None:
        accepted_flag = _resolve_legal_flag(db, token)
        accepted = bool(accepted_flag) if required_enabled else True
        return PortalMeLegal(required_count=0, accepted=accepted, missing=[], required_enabled=required_enabled)

    subject_type, subject_id = subject_info
    if not required_enabled:
        return PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=False)

    service = LegalService(db)
    subject = subject_from_request(subject_type=subject_type, subject_id=subject_id)
    required = service.required_documents(subject=subject, required_codes=required_codes)
    missing_docs = [item["code"] for item in required if not item["accepted"]]
    accepted = not missing_docs
    return PortalMeLegal(
        required_count=len(required),
        accepted=accepted,
        missing=missing_docs,
        required_enabled=required_enabled,
    )


def _load_org_from_orgs(db: Session, *, org_id: int) -> PortalMeOrg | None:
    if not _table_exists(db, "orgs"):
        return None
    orgs = _table(db, "orgs")
    record = db.execute(select(orgs).where(orgs.c.id == org_id)).mappings().first()
    if not record:
        return None
    payload = dict(record)
    return PortalMeOrg(
        id=str(payload.get("id")),
        name=payload.get("name"),
        inn=payload.get("inn"),
        status=payload.get("status"),
        timezone=payload.get("timezone"),
    )


def _load_org_fallback(db: Session, *, client_id: str | None, partner_id: str | None) -> PortalMeOrg | None:
    if client_id:
        if not _is_uuid(client_id):
            return None
        client = db.get(Client, client_id)
        if client:
            crm_client = db.query(CRMClient).filter(CRMClient.id == str(client.id)).one_or_none()
            return PortalMeOrg(
                id=str(client.id),
                name=client.name,
                inn=client.inn,
                status=str(client.status),
                timezone=crm_client.timezone if crm_client else None,
            )
    if partner_id:
        partner = db.query(Partner).filter(Partner.id == str(partner_id)).one_or_none()
        if partner:
            return PortalMeOrg(id=str(partner.id), name=partner.name, status=str(partner.status))
    return None


def _resolve_nav_sections(capabilities: list[str]) -> list[PortalNavSection]:
    sections: list[PortalNavSection] = []
    client_caps = {"CLIENT_CORE", "CLIENT_BILLING", "CLIENT_ANALYTICS"}
    partner_caps = {
        "PARTNER_CORE",
        "PARTNER_PRICING",
        "PARTNER_SETTLEMENTS",
        "PARTNER_FINANCE_VIEW",
        "PARTNER_PAYOUT_REQUEST",
        "PARTNER_CATALOG",
        "PARTNER_ORDERS",
        "PARTNER_ANALYTICS",
    }

    if any(cap in client_caps for cap in capabilities):
        sections.append(PortalNavSection(code="client", label="Client"))
    if any(cap in partner_caps for cap in capabilities):
        sections.append(PortalNavSection(code="partner", label="Partner"))
    return sections


def _resolve_client_contract_status(db: Session, *, client_id: str | None) -> str | None:
    if not client_id or not _is_uuid(client_id):
        return None
    onboarding = (
        db.query(ClientOnboarding)
        .filter(ClientOnboarding.client_id == str(client_id))
        .order_by(ClientOnboarding.updated_at.desc())
        .first()
    )
    if not onboarding or not onboarding.contract_id:
        return None
    contract = (
        db.query(ClientOnboardingContract)
        .filter(ClientOnboardingContract.id == onboarding.contract_id)
        .one_or_none()
    )
    if not contract:
        return None
    return contract.status


def _resolve_onboarding_client_id(db: Session, token: dict) -> str | None:
    owner_id = token.get("user_id") or token.get("sub")
    if not owner_id:
        return None
    onboarding = (
        db.query(ClientOnboarding)
        .filter(ClientOnboarding.owner_user_id == str(owner_id))
        .order_by(ClientOnboarding.created_at.desc())
        .first()
    )
    if not onboarding:
        return None
    return str(onboarding.client_id)


def _resolve_client_subscription(
    db: Session,
    *,
    client_id: str | None,
    existing: PortalMeSubscription | None,
) -> PortalMeSubscription | None:
    if existing and existing.plan_code:
        return existing
    if not client_id or not _is_uuid(client_id):
        return existing
    subscription = get_client_subscription(db, tenant_id=DEFAULT_TENANT_ID, client_id=str(client_id))
    if not subscription:
        return existing
    plan_code = None
    if subscription.plan_id:
        plan = db.get(SubscriptionPlan, subscription.plan_id)
        plan_code = plan.code if plan else None
    return PortalMeSubscription(
        plan_code=plan_code,
        status=str(subscription.status),
        billing_cycle=None,
        support_plan=None,
        slo_tier=None,
        addons=None,
    )


def build_portal_me(db: Session, *, token: dict) -> PortalMeResponse:
    org_id_raw = _resolve_org_id(token)
    client_id = token.get("client_id")
    partner_id = token.get("partner_id")
    if not client_id:
        client_id = _resolve_onboarding_client_id(db, token)
        if client_id and not org_id_raw:
            org_id_raw = client_id
    org_id_int = None
    if org_id_raw is not None:
        try:
            org_id_int = int(org_id_raw)
        except (TypeError, ValueError):
            org_id_int = None

    entitlements_snapshot = None
    org_roles: list[str] = []
    capabilities: list[str] = []
    subscription_payload = None
    if org_id_int is not None:
        snapshot = get_org_entitlements_snapshot(db, org_id=org_id_int)
        entitlements_snapshot = snapshot.entitlements
        org_roles = entitlements_snapshot.get("org_roles") or []
        capabilities = entitlements_snapshot.get("capabilities") or []
        subscription = entitlements_snapshot.get("subscription") or None
        if subscription and "CLIENT" in org_roles:
            subscription_payload = PortalMeSubscription(
                plan_code=subscription.get("plan_code"),
                status=subscription.get("status"),
                billing_cycle=subscription.get("billing_cycle"),
                support_plan=subscription.get("support_plan"),
                slo_tier=subscription.get("slo_tier"),
                addons=subscription.get("addons"),
            )

    if not org_roles:
        if client_id:
            org_roles.append("CLIENT")
        if partner_id:
            org_roles.append("PARTNER")

    subscription_payload = _resolve_client_subscription(
        db,
        client_id=client_id,
        existing=subscription_payload,
    )

    org_payload = None
    if org_id_int is not None:
        org_payload = _load_org_from_orgs(db, org_id=org_id_int)
    if org_payload is None:
        org_payload = _load_org_fallback(db, client_id=client_id, partner_id=partner_id)

    contract_status = _resolve_client_contract_status(db, client_id=client_id)
    employee_timezone = None
    user_id = token.get("user_id") or token.get("sub")
    if user_id and client_id and _is_uuid(user_id):
        employee = (
            db.query(ClientEmployee)
            .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(client_id))
            .one_or_none()
        )
        employee_timezone = employee.timezone if employee else None

    user_roles = _normalize_roles(token)
    nav_sections = _resolve_nav_sections(capabilities)
    scopes = parse_scopes(token)
    actor_type = _resolve_actor_type(token, org_roles)
    flags = {"accepted_legal": _resolve_legal_flag(db, token)}
    legal = _resolve_legal_status(db, token)
    features = PortalMeFeatures(
        onboarding_enabled=settings.CORE_ONBOARDING_ENABLED,
        legal_gate_enabled=settings.LEGAL_GATE_ENABLED,
    )
    gating = PortalMeGating(
        onboarding_enabled=settings.CORE_ONBOARDING_ENABLED,
        legal_gate_enabled=settings.LEGAL_GATE_ENABLED,
    )

    partner_payload = None
    partner_finance_state = None
    partner_legal_state = None
    payout_block_reasons: list[str] = []
    sla_penalties_total = Decimal("0")
    sla_penalties_count = 0
    if (
        "PARTNER" in {str(role).upper() for role in org_roles}
        and org_id_int is not None
        and _table_exists(db, "partner_profiles")
    ):
        profile = ensure_partner_profile(db, org_id=org_id_int, display_name=org_payload.name if org_payload else None)
        if profile in db.new:
            db.commit()
            db.refresh(profile)
        legal_service = PartnerLegalService(db)
        legal_profile = legal_service.get_profile(partner_id=str(org_id_int))
        legal_status_label = "OK"
        if settings.LEGAL_GATE_ENABLED:
            if legal_profile is None:
                legal_status_label = "PENDING"
            elif legal_profile.legal_status == PartnerLegalStatus.VERIFIED:
                legal_status_label = "OK"
            elif legal_profile.legal_status == PartnerLegalStatus.BLOCKED:
                legal_status_label = "REJECTED"
            else:
                legal_status_label = "PENDING"
        legal_block_reason = None
        if settings.LEGAL_GATE_ENABLED:
            try:
                legal_service.ensure_payout_allowed(partner_id=str(org_id_int))
            except PartnerLegalError as exc:
                legal_block_reason = exc.code

        finance_service = PartnerFinanceService(db)
        account = finance_service.get_account(partner_org_id=str(org_id_int), currency="RUB")
        policy = finance_service.get_payout_policy(partner_org_id=str(org_id_int), currency=account.currency)
        threshold = Decimal(policy.min_payout_amount) if policy else Decimal("0")
        partner_finance_state = PortalMePartnerFinanceState(
            balance=Decimal(account.balance_available or 0),
            pending=Decimal(account.balance_pending or 0),
            blocked=Decimal(account.balance_blocked or 0),
            currency=account.currency,
            threshold=threshold,
        )
        partner_legal_state = PortalMePartnerLegalState(
            required_enabled=settings.LEGAL_GATE_ENABLED,
            status=legal_status_label,
            block_reason=legal_block_reason,
        )
        payout_block_reasons = finance_service.evaluate_payout_blockers(
            partner_org_id=str(org_id_int),
            amount=Decimal(account.balance_available or 0),
            currency=account.currency,
            now=datetime.now(timezone.utc),
        )
        penalty_rows = (
            db.query(PartnerLedgerEntry)
            .filter(PartnerLedgerEntry.partner_org_id == str(org_id_int))
            .filter(PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.SLA_PENALTY)
            .all()
        )
        sla_penalties_count = len(penalty_rows)
        if penalty_rows:
            sla_penalties_total = sum((Decimal(entry.amount or 0) for entry in penalty_rows), Decimal("0"))
        partner_payload = PortalMePartner(
            status=profile.status.value if hasattr(profile.status, "value") else str(profile.status),
            profile=PortalMePartnerProfile(
                display_name=profile.display_name,
                contacts_json=profile.contacts_json,
                meta_json=profile.meta_json,
            ),
            finance_state=partner_finance_state,
            legal=partner_legal_state,
        )

    resolved_timezone = employee_timezone or (org_payload.timezone if org_payload else None) or "UTC"
    access_state, access_reason = resolve_access_state(
        actor_type=actor_type,
        org_status=org_payload.status if org_payload else None,
        org_roles=org_roles,
        subscription=subscription_payload,
        legal=legal,
        partner=partner_payload,
        entitlements_snapshot=entitlements_snapshot,
        capabilities=capabilities,
        contract_status=contract_status,
    )
    if actor_type == "partner" and partner_payload:
        if partner_legal_state and partner_legal_state.required_enabled:
            if partner_legal_state.status == "PENDING":
                access_state = PortalAccessState.LEGAL_PENDING
                access_reason = partner_legal_state.block_reason or "legal_pending"
            elif partner_legal_state.status == "REJECTED":
                access_state = PortalAccessState.PAYOUT_BLOCKED
                access_reason = partner_legal_state.block_reason or "legal_rejected"
        if access_state == PortalAccessState.ACTIVE and payout_block_reasons:
            access_state = PortalAccessState.PAYOUT_BLOCKED
            access_reason = payout_block_reasons[0] if payout_block_reasons else "payout_blocked"
        if access_state == PortalAccessState.ACTIVE and sla_penalties_count > 0:
            access_state = PortalAccessState.SLA_PENALTY
            access_reason = "sla_penalty"
    return PortalMeResponse(
        actor_type=actor_type,
        context=actor_type,
        user=PortalMeUser(
            id=str(token.get("user_id") or token.get("sub") or ""),
            email=token.get("email") or token.get("sub"),
            subject_type=token.get("subject_type"),
            timezone=resolved_timezone,
        ),
        org=org_payload,
        org_status=org_payload.status if org_payload else None,
        org_roles=sorted({str(role).upper() for role in org_roles if role}),
        user_roles=user_roles,
        roles=user_roles,
        memberships=sorted({str(role).upper() for role in org_roles if role}),
        scopes=scopes or None,
        flags=flags,
        legal=legal,
        features=features,
        gating=gating,
        subscription=subscription_payload,
        entitlements_snapshot=entitlements_snapshot,
        capabilities=sorted({str(cap) for cap in capabilities if cap}),
        nav_sections=nav_sections or None,
        partner=partner_payload,
        access_state=access_state,
        access_reason=access_reason,
    )


__all__ = ["build_portal_me"]

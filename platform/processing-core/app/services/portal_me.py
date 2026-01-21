from __future__ import annotations

from typing import Any

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.client import Client
from app.models.crm import CRMClient
from app.models.partner import Partner
from app.models.fleet import ClientEmployee
from app.models.legal_acceptance import LegalSubjectType
from app.schemas.portal_me import (
    PortalMeOrg,
    PortalMePartner,
    PortalMePartnerProfile,
    PortalMeResponse,
    PortalMeSubscription,
    PortalMeUser,
    PortalNavSection,
)
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.jwt_support import parse_scopes
from app.services.legal import LegalService, legal_gate_required_codes, subject_from_request
from app.services.partner_core_service import ensure_partner_profile


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


def _resolve_actor_type(token: dict, org_roles: list[str]) -> str:
    if token.get("client_id") or "CLIENT" in org_roles:
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


def _resolve_legal_flag(db: Session, token: dict) -> bool | None:
    subject_info = _resolve_subject(token)
    if subject_info is None:
        return None
    subject_type, subject_id = subject_info
    required_codes = legal_gate_required_codes()
    if not required_codes:
        return True
    service = LegalService(db)
    subject = subject_from_request(subject_type=subject_type, subject_id=subject_id)
    required = service.required_documents(subject=subject, required_codes=required_codes)
    return not any(not item["accepted"] for item in required)


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


def build_portal_me(db: Session, *, token: dict) -> PortalMeResponse:
    org_id_raw = _resolve_org_id(token)
    client_id = token.get("client_id")
    partner_id = token.get("partner_id")
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

    org_payload = None
    if org_id_int is not None:
        org_payload = _load_org_from_orgs(db, org_id=org_id_int)
    if org_payload is None:
        org_payload = _load_org_fallback(db, client_id=client_id, partner_id=partner_id)

    employee_timezone = None
    user_id = token.get("user_id") or token.get("sub")
    if user_id and client_id:
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

    partner_payload = None
    if (
        "PARTNER" in {str(role).upper() for role in org_roles}
        and org_id_int is not None
        and _table_exists(db, "partner_profiles")
    ):
        profile = ensure_partner_profile(db, org_id=org_id_int, display_name=org_payload.name if org_payload else None)
        if profile in db.new:
            db.commit()
            db.refresh(profile)
        partner_payload = PortalMePartner(
            status=profile.status.value if hasattr(profile.status, "value") else str(profile.status),
            profile=PortalMePartnerProfile(
                display_name=profile.display_name,
                contacts_json=profile.contacts_json,
                meta_json=profile.meta_json,
            ),
        )

    return PortalMeResponse(
        actor_type=actor_type,
        user=PortalMeUser(
            id=str(token.get("user_id") or token.get("sub") or ""),
            email=token.get("email") or token.get("sub"),
            subject_type=token.get("subject_type"),
            timezone=employee_timezone,
        ),
        org=org_payload,
        org_roles=sorted({str(role).upper() for role in org_roles if role}),
        user_roles=user_roles,
        scopes=scopes or None,
        flags=flags,
        subscription=subscription_payload,
        entitlements_snapshot=entitlements_snapshot,
        capabilities=sorted({str(cap) for cap in capabilities if cap}),
        nav_sections=nav_sections or None,
        partner=partner_payload,
    )


__all__ = ["build_portal_me"]

from __future__ import annotations

import logging
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
from app.models.legal_acceptance import LegalAcceptance, LegalSubjectType
from app.models.subscriptions_v1 import SubscriptionPlan
from app.schemas.portal_me import (
    PortalMeOrg,
    PortalMePartner,
    PortalMePartnerFinanceState,
    PortalMePartnerLegalState,
    PortalMePartnerProfile,
    PortalMePartnerSlaState,
    PortalMeLegal,
    PortalMeFeatures,
    PortalMeGating,
    PortalMeResponse,
    PortalMeSubscription,
    PortalMeUser,
    PortalNavSection,
    PortalAccessState,
    PortalMeBilling,
    PortalMeBillingInvoice,
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

logger = logging.getLogger(__name__)


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _column_exists(table: Table, name: str) -> bool:
    return name in table.c


def _normalize_roles(token: dict) -> list[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    return sorted({str(role) for role in roles if role})


def _resolve_org_id(token: dict) -> str | None:
    return token.get("org_id") or token.get("client_id") or token.get("partner_id")


def _extract_entitlements_org_id(token: dict) -> str | int | None:
    entitlements = token.get("entitlements_snapshot") or token.get("entitlements") or token.get("entitlements_payload")
    if isinstance(entitlements, dict):
        return entitlements.get("org_id")
    return None


def _resolve_org_id_from_client(db: Session, *, client_id: str | None) -> int | None:
    if not client_id or not _table_exists(db, "orgs"):
        return None
    try:
        orgs = _table(db, "orgs")
    except Exception:
        return None
    client_col = orgs.c.client_id if _column_exists(orgs, "client_id") else None
    if client_col is None and _column_exists(orgs, "client_uuid"):
        client_col = orgs.c.client_uuid
    if client_col is None or not _column_exists(orgs, "id"):
        return None
    try:
        record = db.execute(select(orgs.c.id).where(client_col == client_id)).scalar()
    except Exception:
        return None
    if record is None:
        return None
    try:
        return int(record)
    except (TypeError, ValueError):
        return None


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _resolve_actor_type(token: dict, org_roles: list[str]) -> str:
    normalized_org_roles = {str(role).upper() for role in org_roles if role}
    token_roles = {str(role).upper() for role in _normalize_roles(token)}

    if token.get("client_id") or token.get("subject_type") == "client_user" or "CLIENT" in normalized_org_roles:
        return "client"
    if token.get("partner_id") or "PARTNER" in normalized_org_roles:
        return "partner"

    if any(role.startswith("CLIENT") for role in token_roles):
        return "client"
    if any(role.startswith("PARTNER") for role in token_roles):
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


def _resolve_legal_flag(db: Session, token: dict) -> bool:
    subject_info = _resolve_subject(token)
    if subject_info is None:
        return False
    if not _table_exists(db, "legal_acceptances"):
        return False
    subject_type, subject_id = subject_info
    try:
        accepted = (
            db.query(LegalAcceptance.id)
            .filter(LegalAcceptance.subject_type == subject_type)
            .filter(LegalAcceptance.subject_id == str(subject_id))
            .first()
        )
    except Exception:
        return False
    return accepted is not None


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

    try:
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
    except Exception:
        return PortalMeLegal(required_count=0, accepted=True, missing=[], required_enabled=required_enabled)


def _load_org_from_orgs(db: Session, *, org_id: int) -> PortalMeOrg | None:
    if not _table_exists(db, "orgs"):
        return None
    try:
        orgs = _table(db, "orgs")
        record = db.execute(select(orgs).where(orgs.c.id == org_id)).mappings().first()
        if not record:
            return None
        payload = dict(record)
        return PortalMeOrg(
            id=str(payload.get("id")),
            org_type=payload.get("org_type") or payload.get("type"),
            name=payload.get("name"),
            inn=payload.get("inn"),
            kpp=payload.get("kpp"),
            ogrn=payload.get("ogrn"),
            address=payload.get("address"),
            status=payload.get("status"),
            timezone=payload.get("timezone"),
        )
    except Exception:
        return None


def _load_client_record(db: Session, *, client_id: str | None) -> Client | None:
    if not client_id or not _is_uuid(client_id) or not _table_exists(db, "clients"):
        return None
    try:
        client_uuid = UUID(str(client_id))
        return db.get(Client, client_uuid)
    except Exception:
        return None


def _map_client_to_portal_org(
    db: Session,
    *,
    client: Client,
    onboarding_profile: dict[str, Any] | None,
    onboarding_org_type: str | None,
    onboarding_status: str | None,
) -> PortalMeOrg:
    profile = onboarding_profile or {}
    org_type = profile.get("org_type") or onboarding_org_type
    crm_client = None
    if _table_exists(db, "crm_clients"):
        try:
            crm_client = db.query(CRMClient).filter(CRMClient.id == str(client.id)).one_or_none()
        except Exception:
            crm_client = None
    name = client.name or profile.get("name")
    inn = client.inn or profile.get("inn")
    status = str(client.status) if client.status is not None else None
    if onboarding_profile is not None or onboarding_org_type is not None or onboarding_status is not None:
        status = "ONBOARDING"
    return PortalMeOrg(
        id=str(client.id),
        org_type=org_type,
        name=name,
        inn=inn,
        kpp=profile.get("kpp"),
        ogrn=profile.get("ogrn"),
        address=profile.get("address"),
        status=status,
        timezone=crm_client.timezone if crm_client else None,
    )


def _load_org_fallback(
    db: Session,
    *,
    partner_id: str | None,
) -> PortalMeOrg | None:
    if partner_id:
        partner = db.query(Partner).filter(Partner.id == str(partner_id)).one_or_none()
        if partner:
            return PortalMeOrg(
                id=str(partner.id),
                name=partner.name,
                status=str(partner.status),
            )
    return None


def _empty_entitlements_snapshot(*, org_id: str | int | None) -> dict[str, Any]:
    computed_at = datetime.now(timezone.utc).isoformat()
    return {
        "org_id": org_id,
        "subscription": None,
        "org_roles": [],
        "features": {},
        "modules": {},
        "limits": {},
        "capabilities": [],
        "computed": {
            "hash": "",
            "computed_at": computed_at,
        },
    }


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
    if not _table_exists(db, "client_onboarding") or not _table_exists(db, "client_onboarding_contracts"):
        return None
    try:
        onboarding = (
            db.query(ClientOnboarding)
            .filter(ClientOnboarding.client_id == str(client_id))
            .order_by(ClientOnboarding.updated_at.desc())
            .first()
        )
    except Exception:
        return None
    if not onboarding or not onboarding.contract_id:
        return None
    try:
        contract = (
            db.query(ClientOnboardingContract)
            .filter(ClientOnboardingContract.id == onboarding.contract_id)
            .one_or_none()
        )
    except Exception:
        contract = None
    if not contract:
        return None
    return contract.status


def _resolve_overdue_invoices(db: Session, *, org_id: int | None) -> list[PortalMeBillingInvoice]:
    if org_id is None or not _table_exists(db, "billing_invoices"):
        return []
    billing_invoices = _table(db, "billing_invoices")
    status_col = billing_invoices.c.status if _column_exists(billing_invoices, "status") else None
    due_at_col = billing_invoices.c.due_at if _column_exists(billing_invoices, "due_at") else None
    org_id_col = billing_invoices.c.org_id if _column_exists(billing_invoices, "org_id") else None
    if org_id_col is None:
        return []

    now = datetime.now(timezone.utc)
    query = select(billing_invoices).where(org_id_col == org_id)
    if status_col is not None:
        query = query.where(status_col.notin_(["PAID", "VOID"]))
    if due_at_col is not None:
        query = query.order_by(due_at_col.asc().nullslast())
    rows = db.execute(query).mappings().all()
    overdue_items: list[PortalMeBillingInvoice] = []
    for row in rows:
        status = row.get("status")
        due_at = row.get("due_at")
        is_overdue = bool(status in {"OVERDUE"} or (due_at and due_at <= now))
        if not is_overdue:
            continue
        amount = row.get("total_amount")
        if amount is None:
            amount = row.get("amount_total")
        number = row.get("invoice_number") or row.get("number") or str(row.get("id"))
        overdue_items.append(
            PortalMeBillingInvoice(
                id=row.get("id"),
                number=str(number) if number is not None else None,
                amount=amount,
                currency=row.get("currency"),
                due_at=due_at,
                download_url=f"/api/core/client/invoices/{row.get('id')}/download" if row.get("id") else None,
                status=status,
            )
        )
    return overdue_items


def _resolve_onboarding_client_id(db: Session, token: dict) -> str | None:
    owner_id = token.get("user_id") or token.get("sub")
    if not owner_id:
        return None
    if not _table_exists(db, "client_onboarding"):
        return None
    try:
        onboarding = (
            db.query(ClientOnboarding)
            .filter(ClientOnboarding.owner_user_id == str(owner_id))
            .order_by(ClientOnboarding.created_at.desc())
            .first()
        )
    except Exception:
        return None
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
    try:
        subscription = get_client_subscription(db, tenant_id=DEFAULT_TENANT_ID, client_id=str(client_id))
    except Exception:
        subscription = None
    if not subscription:
        return existing
    plan_code = None
    if subscription.plan_id:
        try:
            plan = db.get(SubscriptionPlan, subscription.plan_id)
        except Exception:
            plan = None
        plan_code = plan.code if plan else None
    return PortalMeSubscription(
        plan_code=plan_code,
        status=str(subscription.status),
        billing_cycle=None,
        support_plan=None,
        slo_tier=None,
        addons=None,
    )


def _resolve_onboarding_profile(
    db: Session,
    *,
    client_id: str | None,
    owner_id: str | None,
) -> tuple[ClientOnboarding | None, dict[str, Any] | None]:
    if not client_id or not owner_id:
        return None, None
    if not _table_exists(db, "client_onboarding"):
        return None, None
    try:
        onboarding = (
            db.query(ClientOnboarding)
            .filter(ClientOnboarding.client_id == str(client_id))
            .filter(ClientOnboarding.owner_user_id == str(owner_id))
            .order_by(ClientOnboarding.updated_at.desc())
            .first()
        )
    except Exception:
        return None, None
    if not onboarding:
        return None, None
    profile = onboarding.profile_json if onboarding.profile_json else None
    return onboarding, profile


def _is_client_profile_complete(
    *,
    client: Client | None,
    onboarding_profile: dict[str, Any] | None,
    onboarding: ClientOnboarding | None,
) -> bool | None:
    if not client:
        return False
    name = (client.name or "").strip()
    inn = (client.inn or "").strip()
    org_type = None
    if onboarding_profile:
        org_type = onboarding_profile.get("org_type")
    if not org_type and onboarding and onboarding.client_type:
        org_type = onboarding.client_type
    org_type = str(org_type).strip() if org_type else ""
    return bool(name and inn and org_type)


def build_portal_me(db: Session, *, token: dict) -> PortalMeResponse:
    portal_me_failed = False
    client_id = token.get("client_id")
    partner_id = token.get("partner_id")
    org_roles: list[str] = []
    capabilities: list[str] = []
    subscription_payload = None
    actor_type = _resolve_actor_type(token, org_roles)

    org_id_raw = None
    if actor_type == "client":
        if not client_id:
            client_id = _resolve_onboarding_client_id(db, token)
        org_id_raw = client_id
    else:
        org_id_raw = _resolve_org_id(token)
        if not org_id_raw:
            entitlements_org_id = _extract_entitlements_org_id(token)
            if entitlements_org_id is not None:
                org_id_raw = str(entitlements_org_id)
    if not client_id and org_id_raw and _is_uuid(str(org_id_raw)):
        client_id = str(org_id_raw)

    org_id_int = None
    if org_id_raw is not None:
        try:
            org_id_int = int(org_id_raw)
        except (TypeError, ValueError):
            org_id_int = None
    if actor_type != "client" and org_id_int is None and client_id:
        org_id_int = _resolve_org_id_from_client(db, client_id=client_id)

    entitlements_snapshot = None
    if actor_type != "client" and org_id_int is not None:
        try:
            snapshot = get_org_entitlements_snapshot(db, org_id=org_id_int)
        except Exception:
            logger.exception("portal_me_entitlements_failed", extra={"org_id": org_id_int})
            snapshot = None
        if snapshot:
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
    elif actor_type == "client":
        snapshot_payload = token.get("entitlements_snapshot") or token.get("entitlements") or token.get(
            "entitlements_payload"
        )
        if isinstance(snapshot_payload, dict):
            entitlements_snapshot = dict(snapshot_payload)
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

    try:
        subscription_payload = _resolve_client_subscription(
            db,
            client_id=client_id,
            existing=subscription_payload,
        )
    except Exception:
        subscription_payload = subscription_payload

    owner_user_id = token.get("user_id") or token.get("sub")
    try:
        onboarding, onboarding_profile = _resolve_onboarding_profile(
            db,
            client_id=str(client_id) if client_id else None,
            owner_id=str(owner_user_id) if owner_user_id else None,
        )
    except Exception:
        onboarding = None
        onboarding_profile = None
    onboarding_profile_complete = None
    if actor_type == "client":
        client_record = _load_client_record(db, client_id=str(client_id) if client_id else None)
        onboarding_profile_complete = _is_client_profile_complete(
            client=client_record,
            onboarding_profile=onboarding_profile,
            onboarding=onboarding,
        )
    else:
        client_record = None

    org_payload = None
    if actor_type == "client":
        if client_record:
            org_payload = _map_client_to_portal_org(
                db,
                client=client_record,
                onboarding_profile=onboarding_profile,
                onboarding_org_type=onboarding.client_type if onboarding else None,
                onboarding_status=onboarding.status if onboarding else None,
            )
    else:
        try:
            if org_id_int is not None:
                org_payload = _load_org_from_orgs(db, org_id=org_id_int)
        except Exception:
            org_payload = None
        if org_payload is None:
            try:
                org_payload = _load_org_fallback(
                    db,
                    partner_id=partner_id,
                )
            except Exception:
                org_payload = None

    if entitlements_snapshot is not None and isinstance(entitlements_snapshot, dict):
        if actor_type == "client":
            entitlements_org_id = client_id or (org_payload.id if org_payload else None)
            entitlements_snapshot = {
                **entitlements_snapshot,
                "org_id": entitlements_org_id,
            }
        elif org_payload and org_payload.id and not entitlements_snapshot.get("org_id"):
            entitlements_snapshot = {**entitlements_snapshot, "org_id": org_payload.id}
    contract_status = None
    try:
        if onboarding and onboarding.contract_id and _table_exists(db, "client_onboarding_contracts"):
            try:
                contract = (
                    db.query(ClientOnboardingContract)
                    .filter(ClientOnboardingContract.id == onboarding.contract_id)
                    .one_or_none()
                )
            except Exception:
                contract = None
            contract_status = contract.status if contract else None
        if contract_status is None:
            contract_status = _resolve_client_contract_status(db, client_id=client_id)
    except Exception:
        contract_status = None
    if entitlements_snapshot is None:
        org_id_value = None
        if actor_type == "client" and client_id:
            org_id_value = str(client_id)
        elif org_payload and org_payload.id:
            org_id_value = org_payload.id
        elif actor_type != "client" and org_id_raw:
            org_id_value = str(org_id_raw)
        entitlements_snapshot = _empty_entitlements_snapshot(org_id=org_id_value)

    if actor_type == "client":
        if org_payload:
            normalized_roles = {str(role).upper() for role in org_roles if role}
            if "CLIENT" not in normalized_roles:
                normalized_roles.add("CLIENT")
            org_roles = sorted(normalized_roles)
        else:
            org_roles = []
    elif not org_roles:
        if client_id:
            org_roles.append("CLIENT")
        if partner_id:
            org_roles.append("PARTNER")

    employee_timezone = None
    user_id = token.get("user_id") or token.get("sub")
    if user_id and client_id and _is_uuid(user_id) and _table_exists(db, "client_employees"):
        try:
            employee = (
                db.query(ClientEmployee)
                .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(client_id))
                .one_or_none()
            )
        except Exception:
            employee = None
        employee_timezone = employee.timezone if employee else None

    user_roles = _normalize_roles(token)
    nav_sections = _resolve_nav_sections(capabilities)
    scopes = parse_scopes(token)
    actor_type = _resolve_actor_type(token, org_roles)
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
    if "PARTNER" in {str(role).upper() for role in org_roles} and org_id_int is not None:
        try:
            if _table_exists(db, "partner_profiles"):
                profile = ensure_partner_profile(
                    db,
                    org_id=org_id_int,
                    display_name=org_payload.name if org_payload else None,
                )
                if profile in db.new:
                    db.commit()
                    db.refresh(profile)
                legal_service = PartnerLegalService(db)
                legal_profile = (
                    legal_service.get_profile(partner_id=str(org_id_int))
                    if _table_exists(db, "partner_legal_profiles")
                    else None
                )
                legal_status_label = "VERIFIED"
                if settings.LEGAL_GATE_ENABLED:
                    if legal_profile is None:
                        legal_status_label = "PENDING"
                    elif legal_profile.legal_status == PartnerLegalStatus.VERIFIED:
                        legal_status_label = "VERIFIED"
                    elif legal_profile.legal_status == PartnerLegalStatus.BLOCKED:
                        legal_status_label = "REJECTED"
                    else:
                        legal_status_label = "PENDING"
                legal_block_reason = None
                if (
                    settings.LEGAL_GATE_ENABLED
                    and _table_exists(db, "partner_legal_profiles")
                    and _table_exists(db, "partner_legal_details")
                ):
                    try:
                        legal_service.ensure_payout_allowed(partner_id=str(org_id_int))
                    except PartnerLegalError as exc:
                        legal_block_reason = exc.code

                finance_service = PartnerFinanceService(db)
                account = None
                if _table_exists(db, "partner_accounts"):
                    account = finance_service.get_account(partner_org_id=str(org_id_int), currency="RUB")
                policy = None
                if account is not None and _table_exists(db, "partner_payout_policies"):
                    policy = finance_service.get_payout_policy(partner_org_id=str(org_id_int), currency=account.currency)
                threshold = Decimal(policy.min_payout_amount) if policy else Decimal("0")
                if account is not None:
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
                if (
                    account is not None
                    and _table_exists(db, "partner_payout_policies")
                    and _table_exists(db, "partner_payout_requests")
                    and _table_exists(db, "disputes")
                    and _table_exists(db, "operations")
                ):
                    payout_block_reasons = finance_service.evaluate_payout_blockers(
                        partner_org_id=str(org_id_int),
                        amount=Decimal(account.balance_available or 0),
                        currency=account.currency,
                        now=datetime.now(timezone.utc),
                    )
                if _table_exists(db, "partner_ledger_entries"):
                    penalty_rows = (
                        db.query(PartnerLedgerEntry)
                        .filter(PartnerLedgerEntry.partner_org_id == str(org_id_int))
                        .filter(PartnerLedgerEntry.entry_type == PartnerLedgerEntryType.SLA_PENALTY)
                        .all()
                    )
                    sla_penalties_count = len(penalty_rows)
                    if penalty_rows:
                        sla_penalties_total = sum((Decimal(entry.amount or 0) for entry in penalty_rows), Decimal("0"))
                sla_state = PortalMePartnerSlaState(
                    penalty_active=sla_penalties_count > 0,
                    penalty_amount=sla_penalties_total,
                )
                partner_payload = PortalMePartner(
                    status=profile.status.value if hasattr(profile.status, "value") else str(profile.status),
                    profile=PortalMePartnerProfile(
                        display_name=profile.display_name,
                        contacts_json=profile.contacts_json,
                        meta_json=profile.meta_json,
                    ),
                    finance_state=partner_finance_state,
                    legal=partner_legal_state,
                    legal_state=partner_legal_state,
                    sla_state=sla_state,
                )
        except Exception:
            partner_payload = None

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
        onboarding_profile_complete=onboarding_profile_complete,
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
    billing_payload = None
    if actor_type == "client" and access_state == PortalAccessState.OVERDUE:
        overdue_invoices = _resolve_overdue_invoices(db, org_id=org_id_int)
        billing_payload = PortalMeBilling(overdue_invoices=overdue_invoices, next_action="PAY_INVOICE")
    flags = {"accepted_legal": _resolve_legal_flag(db, token), "portal_me_failed": portal_me_failed}
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
        billing=billing_payload,
    )


__all__ = ["build_portal_me"]

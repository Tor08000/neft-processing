from __future__ import annotations

from collections.abc import Iterable

from .permissions import Permission

CANONICAL_ROLES = {
    "admin",
    "client_user",
    "partner_user",
    "client_admin",
    "partner_admin",
}

ROLE_PERMISSIONS = {
    "admin": {
        Permission.ADMIN_CONTRACTS_ALL.value,
        Permission.ADMIN_BILLING_ALL.value,
        Permission.ADMIN_RECONCILIATION_ALL.value,
        Permission.ADMIN_SETTLEMENT_ALL.value,
        Permission.ADMIN_AUDIT_ALL.value,
        Permission.ADMIN_MARKETPLACE_SPONSORED_ALL.value,
        Permission.CLIENT_DASHBOARD_VIEW.value,
        Permission.CLIENT_INVOICES_LIST.value,
        Permission.CLIENT_INVOICES_VIEW.value,
        Permission.CLIENT_INVOICES_DOWNLOAD.value,
        Permission.CLIENT_CONTRACTS_LIST.value,
        Permission.CLIENT_CONTRACTS_VIEW.value,
        Permission.CLIENT_SLA_VIEW.value,
        Permission.PARTNER_DASHBOARD_VIEW.value,
        Permission.PARTNER_CONTRACTS_LIST.value,
        Permission.PARTNER_CONTRACTS_VIEW.value,
        Permission.PARTNER_SETTLEMENTS_LIST.value,
        Permission.PARTNER_SETTLEMENTS_VIEW.value,
        Permission.PARTNER_PAYOUTS_LIST.value,
        Permission.PARTNER_PAYOUTS_CONFIRM.value,
        Permission.PARTNER_CATALOG_ALL.value,
    },
    "client_user": {
        Permission.CLIENT_DASHBOARD_VIEW.value,
        Permission.CLIENT_INVOICES_LIST.value,
        Permission.CLIENT_INVOICES_VIEW.value,
        Permission.CLIENT_INVOICES_DOWNLOAD.value,
        Permission.CLIENT_CONTRACTS_LIST.value,
        Permission.CLIENT_CONTRACTS_VIEW.value,
        Permission.CLIENT_SLA_VIEW.value,
        Permission.CLIENT_FLEET_CARDS_LIST.value,
        Permission.CLIENT_FLEET_CARDS_VIEW.value,
        Permission.CLIENT_FLEET_GROUPS_LIST.value,
        Permission.CLIENT_FLEET_GROUPS_MANAGE.value,
        Permission.CLIENT_FLEET_LIMITS_MANAGE.value,
        Permission.CLIENT_FLEET_SPEND_VIEW.value,
        Permission.CLIENT_MARKETPLACE_VIEW.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_LIST.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_VIEW.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_CREATE.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_CANCEL.value,
    },
    "partner_user": {
        Permission.PARTNER_DASHBOARD_VIEW.value,
        Permission.PARTNER_CONTRACTS_LIST.value,
        Permission.PARTNER_CONTRACTS_VIEW.value,
        Permission.PARTNER_SETTLEMENTS_LIST.value,
        Permission.PARTNER_SETTLEMENTS_VIEW.value,
        Permission.PARTNER_PAYOUTS_LIST.value,
        Permission.PARTNER_CATALOG_ALL.value,
        Permission.PARTNER_MARKETPLACE_ORDERS_ALL.value,
        Permission.PARTNER_MARKETPLACE_SPONSORED_ALL.value,
    },
    "client_admin": {
        Permission.CLIENT_DASHBOARD_VIEW.value,
        Permission.CLIENT_INVOICES_LIST.value,
        Permission.CLIENT_INVOICES_VIEW.value,
        Permission.CLIENT_INVOICES_DOWNLOAD.value,
        Permission.CLIENT_CONTRACTS_LIST.value,
        Permission.CLIENT_CONTRACTS_VIEW.value,
        Permission.CLIENT_SLA_VIEW.value,
        Permission.CLIENT_FLEET_CARDS_LIST.value,
        Permission.CLIENT_FLEET_CARDS_VIEW.value,
        Permission.CLIENT_FLEET_CARDS_MANAGE.value,
        Permission.CLIENT_FLEET_GROUPS_LIST.value,
        Permission.CLIENT_FLEET_GROUPS_MANAGE.value,
        Permission.CLIENT_FLEET_LIMITS_MANAGE.value,
        Permission.CLIENT_FLEET_SPEND_VIEW.value,
        Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value,
        Permission.CLIENT_MARKETPLACE_VIEW.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_LIST.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_VIEW.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_CREATE.value,
        Permission.CLIENT_MARKETPLACE_ORDERS_CANCEL.value,
    },
    "partner_admin": {
        Permission.PARTNER_DASHBOARD_VIEW.value,
        Permission.PARTNER_CONTRACTS_LIST.value,
        Permission.PARTNER_CONTRACTS_VIEW.value,
        Permission.PARTNER_SETTLEMENTS_LIST.value,
        Permission.PARTNER_SETTLEMENTS_VIEW.value,
        Permission.PARTNER_PAYOUTS_LIST.value,
        Permission.PARTNER_PAYOUTS_CONFIRM.value,
        Permission.PARTNER_CATALOG_ALL.value,
        Permission.PARTNER_MARKETPLACE_ORDERS_ALL.value,
        Permission.PARTNER_MARKETPLACE_SPONSORED_ALL.value,
    },
}


def _canonical_role_from_raw(raw_role: str) -> str | None:
    normalized = raw_role.strip().replace("-", "_").upper()
    if not normalized:
        return None
    if normalized == "SUPERADMIN" or normalized.startswith("ADMIN"):
        return "admin"
    if normalized.startswith("CLIENT_ADMIN"):
        return "client_admin"
    if normalized.startswith("CLIENT"):
        return "client_user"
    if normalized.startswith("PARTNER_ADMIN"):
        return "partner_admin"
    if normalized.startswith("PARTNER"):
        return "partner_user"
    return None


def canonicalize_roles(raw_roles: Iterable[str]) -> set[str]:
    roles: set[str] = set()
    for raw in raw_roles:
        role = _canonical_role_from_raw(str(raw))
        if role:
            roles.add(role)
    return roles


def canonical_role_for_subject_type(subject_type: str | None) -> str | None:
    if not subject_type:
        return None
    normalized = subject_type.strip().lower()
    if normalized == "client_user":
        return "client_user"
    if normalized == "partner_user":
        return "partner_user"
    return None


__all__ = [
    "CANONICAL_ROLES",
    "ROLE_PERMISSIONS",
    "canonical_role_for_subject_type",
    "canonicalize_roles",
]

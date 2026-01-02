from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    CLIENT_DASHBOARD_VIEW = "client:dashboard:view"
    CLIENT_INVOICES_LIST = "client:invoices:list"
    CLIENT_INVOICES_VIEW = "client:invoices:view"
    CLIENT_INVOICES_DOWNLOAD = "client:invoices:download"
    CLIENT_CONTRACTS_LIST = "client:contracts:list"
    CLIENT_CONTRACTS_VIEW = "client:contracts:view"
    CLIENT_SLA_VIEW = "client:sla:view"

    PARTNER_DASHBOARD_VIEW = "partner:dashboard:view"
    PARTNER_CONTRACTS_LIST = "partner:contracts:list"
    PARTNER_CONTRACTS_VIEW = "partner:contracts:view"
    PARTNER_SETTLEMENTS_LIST = "partner:settlements:list"
    PARTNER_SETTLEMENTS_VIEW = "partner:settlements:view"
    PARTNER_PAYOUTS_LIST = "partner:payouts:list"
    PARTNER_PAYOUTS_CONFIRM = "partner:payouts:confirm"

    ADMIN_CONTRACTS_ALL = "admin:contracts:*"
    ADMIN_BILLING_ALL = "admin:billing:*"
    ADMIN_RECONCILIATION_ALL = "admin:reconciliation:*"
    ADMIN_SETTLEMENT_ALL = "admin:settlement:*"
    ADMIN_AUDIT_ALL = "admin:audit:*"


ALL_PERMISSIONS = {permission.value for permission in Permission}


__all__ = ["ALL_PERMISSIONS", "Permission"]

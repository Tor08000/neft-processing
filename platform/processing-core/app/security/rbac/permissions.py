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
    CLIENT_FLEET_CARDS_LIST = "client:fleet:cards:list"
    CLIENT_FLEET_CARDS_VIEW = "client:fleet:cards:view"
    CLIENT_FLEET_CARDS_MANAGE = "client:fleet:cards:manage"
    CLIENT_FLEET_GROUPS_LIST = "client:fleet:groups:list"
    CLIENT_FLEET_GROUPS_MANAGE = "client:fleet:groups:manage"
    CLIENT_FLEET_LIMITS_MANAGE = "client:fleet:limits:manage"
    CLIENT_FLEET_SPEND_VIEW = "client:fleet:spend:view"
    CLIENT_FLEET_EMPLOYEES_MANAGE = "client:fleet:employees:manage"
    CLIENT_MARKETPLACE_VIEW = "client:marketplace:view"
    CLIENT_MARKETPLACE_ORDERS_LIST = "client:marketplace:orders:list"
    CLIENT_MARKETPLACE_ORDERS_VIEW = "client:marketplace:orders:view"
    CLIENT_MARKETPLACE_ORDERS_CREATE = "client:marketplace:orders:create"
    CLIENT_MARKETPLACE_ORDERS_CANCEL = "client:marketplace:orders:cancel"
    CLIENT_BOOKINGS_LIST = "client:bookings:list"
    CLIENT_BOOKINGS_VIEW = "client:bookings:view"
    CLIENT_BOOKINGS_CREATE = "client:bookings:create"
    CLIENT_BOOKINGS_CANCEL = "client:bookings:cancel"

    PARTNER_DASHBOARD_VIEW = "partner:dashboard:view"
    PARTNER_CONTRACTS_LIST = "partner:contracts:list"
    PARTNER_CONTRACTS_VIEW = "partner:contracts:view"
    PARTNER_SETTLEMENTS_LIST = "partner:settlements:list"
    PARTNER_SETTLEMENTS_VIEW = "partner:settlements:view"
    PARTNER_PAYOUTS_LIST = "partner:payouts:list"
    PARTNER_PAYOUTS_CONFIRM = "partner:payouts:confirm"
    PARTNER_CATALOG_ALL = "partner:catalog:*"
    PARTNER_MARKETPLACE_ORDERS_ALL = "partner:marketplace:orders:*"
    PARTNER_MARKETPLACE_PROMOTIONS_ALL = "partner:marketplace:promotions:*"
    PARTNER_MARKETPLACE_SPONSORED_ALL = "partner:marketplace:sponsored:*"
    PARTNER_GAMIFICATION_ALL = "partner:gamification:*"
    PARTNER_BOOKINGS_ALL = "partner:bookings:*"
    PARTNER_PROFILE_VIEW = "partner:profile:view"
    PARTNER_PROFILE_MANAGE = "partner:profile:manage"
    PARTNER_OFFERS_LIST = "partner:offers:list"
    PARTNER_OFFERS_MANAGE = "partner:offers:manage"
    PARTNER_ORDERS_LIST = "partner:orders:list"
    PARTNER_ORDERS_VIEW = "partner:orders:view"
    PARTNER_ORDERS_UPDATE = "partner:orders:update"
    PARTNER_ANALYTICS_VIEW = "partner:analytics:view"

    ADMIN_CONTRACTS_ALL = "admin:contracts:*"
    ADMIN_BILLING_ALL = "admin:billing:*"
    ADMIN_RECONCILIATION_ALL = "admin:reconciliation:*"
    ADMIN_SETTLEMENT_ALL = "admin:settlement:*"
    ADMIN_AUDIT_ALL = "admin:audit:*"
    ADMIN_MARKETPLACE_SPONSORED_ALL = "admin:marketplace:sponsored:*"
    ADMIN_BOOKINGS_ALL = "admin:bookings:*"


ALL_PERMISSIONS = {permission.value for permission in Permission}


__all__ = ["ALL_PERMISSIONS", "Permission"]

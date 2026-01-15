from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANONICAL_ROLE_MAP = {
    "CLIENT_OWNER": "OWNER",
    "CLIENT_ADMIN": "ADMIN",
    "CLIENT_ACCOUNTANT": "ACCOUNTANT",
    "CLIENT_USER": "DRIVER",
    "OWNER": "OWNER",
    "ADMIN": "ADMIN",
    "ACCOUNTANT": "ACCOUNTANT",
    "FLEET_MANAGER": "FLEET_MANAGER",
    "DRIVER": "DRIVER",
    "LOGISTICIAN": "LOGISTICIAN",
}

ROLE_PERMISSIONS = {
    "OWNER": {"*"},
    "ADMIN": {"*"},
    "ACCOUNTANT": {"billing:view", "billing:download", "docs:view"},
    "FLEET_MANAGER": {"fleet:view", "fleet:manage", "cards:manage"},
    "DRIVER": {"cards:view", "operations:view"},
    "LOGISTICIAN": {"logistics:view"},
}


@dataclass(frozen=True)
class ClientEntitlements:
    enabled_modules: list[str]
    permissions: list[str]
    limits: dict[str, dict[str, Any]]
    org_status: str


def normalize_roles(roles: list[str]) -> list[str]:
    normalized = []
    for role in roles:
        if not role:
            continue
        normalized_role = CANONICAL_ROLE_MAP.get(str(role).upper(), str(role).upper())
        if normalized_role not in normalized:
            normalized.append(normalized_role)
    return normalized


def _permissions_from_role_entitlements(role_entitlements: list[dict[str, Any]]) -> set[str]:
    permissions: set[str] = set()
    for entitlements in role_entitlements:
        if not entitlements:
            continue
        scope = entitlements.get("scope")
        if scope == "all":
            permissions.add("*")
        permissions.update(entitlements.get("permissions", []) or [])
    return permissions


def _permissions_from_roles(roles: list[str]) -> set[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return permissions


def build_client_entitlements(
    *,
    roles: list[str],
    org_status: str,
    modules: dict[str, dict[str, Any]],
    limits: dict[str, dict[str, Any]],
    role_entitlements: list[dict[str, Any]] | None = None,
) -> ClientEntitlements:
    if org_status != "ACTIVE":
        return ClientEntitlements(enabled_modules=[], permissions=[], limits=limits, org_status=org_status)

    enabled_modules = sorted([code for code, data in modules.items() if data.get("enabled")])
    normalized_roles = normalize_roles(roles)
    role_permissions = _permissions_from_roles(normalized_roles)
    entitlements_permissions = _permissions_from_role_entitlements(role_entitlements or [])
    permissions = sorted(role_permissions.union(entitlements_permissions))
    return ClientEntitlements(
        enabled_modules=enabled_modules,
        permissions=permissions,
        limits=limits,
        org_status=org_status,
    )


__all__ = ["ClientEntitlements", "build_client_entitlements", "normalize_roles"]

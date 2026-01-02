from __future__ import annotations

import os

from .permissions import ALL_PERMISSIONS
from .principal import Principal
from .roles import ROLE_PERMISSIONS

ALLOW_SCOPE_PERMISSIONS = os.getenv("RBAC_ALLOW_SCOPE_PERMISSIONS", "false").lower() in {
    "1",
    "true",
    "yes",
}


def _matches_permission(granted: str, required: str) -> bool:
    if granted == required:
        return True
    if granted.endswith(":*"):
        prefix = granted[:-1]
        return required.startswith(prefix)
    return False


def _permissions_for_roles(roles: set[str]) -> set[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return permissions


def has_permission(principal: Principal, permission: str) -> bool:
    if permission not in ALL_PERMISSIONS:
        return False

    if principal.is_admin:
        return True

    if ALLOW_SCOPE_PERMISSIONS and permission in principal.scopes:
        return True

    granted = _permissions_for_roles(principal.roles)
    return any(_matches_permission(granted_permission, permission) for granted_permission in granted)


__all__ = ["ALLOW_SCOPE_PERMISSIONS", "has_permission"]

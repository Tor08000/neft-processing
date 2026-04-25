from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.admin_rbac import extract_admin_roles
from app.services.admin_portal_access import admin_capability_allows


def require_admin_capability(capability: str, action: str = "read"):
    def _dependency(token: dict = Depends(require_admin_user)) -> dict:
        roles = extract_admin_roles(token)
        if not admin_capability_allows(roles, capability, action):
            raise HTTPException(status_code=403, detail="forbidden_admin_role")
        return token

    return _dependency


__all__ = ["require_admin_capability"]

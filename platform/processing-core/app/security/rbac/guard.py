from __future__ import annotations

from fastapi import Depends, HTTPException

from .policy import has_permission
from .principal import Principal, get_principal


def _forbidden_detail(reason: str, *, permission: str | None = None) -> dict:
    payload = {"error": "forbidden", "reason": reason}
    if permission:
        payload["permission"] = permission
    return payload


def require_permission(permission: str):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not has_permission(principal, permission):
            raise HTTPException(
                status_code=403,
                detail=_forbidden_detail("missing_permission", permission=permission),
            )
        return principal

    return dep


__all__ = ["require_permission"]

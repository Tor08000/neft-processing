from __future__ import annotations

from typing import Iterable

from fastapi import Depends, HTTPException

from app.api.dependencies.admin import require_admin_user


def _normalize_roles(raw_roles: Iterable[str]) -> set[str]:
    return {str(role).upper() for role in raw_roles if role}


def extract_admin_roles(token: dict) -> list[str]:
    role_items: list[str] = []
    role = token.get("role")
    if role:
        role_items.append(str(role))
    roles = token.get("roles") or []
    if isinstance(roles, str):
        role_items.append(roles)
    else:
        role_items.extend([str(item) for item in roles if item])
    normalized = sorted(_normalize_roles(role_items))
    return normalized


def require_admin_role(role: str):
    required = role.upper()

    def _dependency(token: dict = Depends(require_admin_user)) -> dict:
        roles = _normalize_roles(extract_admin_roles(token))
        if required not in roles:
            raise HTTPException(
                status_code=403,
                detail={"message": "Insufficient role", "required_roles": [role]},
            )
        return token

    return _dependency


def require_any_admin_roles(roles: list[str]):
    required_roles = [role.upper() for role in roles]

    def _dependency(token: dict = Depends(require_admin_user)) -> dict:
        roles_set = _normalize_roles(extract_admin_roles(token))
        if roles_set.intersection({"SUPERADMIN", "PLATFORM_ADMIN", "ADMIN", "NEFT_SUPERADMIN", "NEFT_ADMIN"}):
            return token
        if not roles_set.intersection(required_roles):
            raise HTTPException(
                status_code=403,
                detail={"message": "Insufficient role", "required_roles": roles},
            )
        return token

    return _dependency


__all__ = ["extract_admin_roles", "require_admin_role", "require_any_admin_roles"]

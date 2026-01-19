from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.admin_rbac import extract_admin_roles


class AdminPermission(BaseModel):
    read: bool
    write: bool


class AdminPermissions(BaseModel):
    ops: AdminPermission
    finance: AdminPermission
    sales: AdminPermission
    legal: AdminPermission
    superadmin: AdminPermission


class AdminEnv(BaseModel):
    name: str
    build: str
    region: str


class AdminUser(BaseModel):
    id: str
    email: str | None
    roles: list[str]
    issuer: str | None


class AdminMeResponse(BaseModel):
    admin_user: AdminUser
    permissions: AdminPermissions
    env: AdminEnv


router = APIRouter()


def _normalize_env_name(raw: str) -> str:
    value = raw.lower()
    if value in {"local", "dev"}:
        return "dev"
    if "stage" in value:
        return "stage"
    if "prod" in value:
        return "prod"
    return value


def _build_permissions(roles: list[str]) -> AdminPermissions:
    role_set = {role.upper() for role in roles}
    ops = AdminPermission(read="NEFT_OPS" in role_set, write=False)
    finance = AdminPermission(read="NEFT_FINANCE" in role_set, write="NEFT_FINANCE" in role_set)
    sales = AdminPermission(read="NEFT_SALES" in role_set, write=False)
    legal = AdminPermission(read="NEFT_LEGAL" in role_set, write=False)
    superadmin_enabled = bool(role_set.intersection({"NEFT_SUPERADMIN", "NEFT_ADMIN", "ADMIN"}))
    superadmin = AdminPermission(read=superadmin_enabled, write=superadmin_enabled)

    if superadmin_enabled:
        ops = AdminPermission(read=True, write=True)
        finance = AdminPermission(read=True, write=True)
        sales = AdminPermission(read=True, write=True)
        legal = AdminPermission(read=True, write=True)

    return AdminPermissions(
        ops=ops,
        finance=finance,
        sales=sales,
        legal=legal,
        superadmin=superadmin,
    )


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(token: dict = Depends(require_admin_user)) -> AdminMeResponse:
    roles = extract_admin_roles(token)
    user_id = token.get("user_id") or token.get("sub") or token.get("uid") or "unknown"
    admin_user = AdminUser(
        id=str(user_id),
        email=token.get("email"),
        roles=roles,
        issuer=token.get("iss"),
    )
    permissions = _build_permissions(roles)
    env = AdminEnv(
        name=_normalize_env_name(os.getenv("NEFT_ENV", "dev")),
        build=os.getenv("GIT_SHA", os.getenv("BUILD_SHA", "unknown")),
        region=os.getenv("NEFT_REGION", "local"),
    )
    return AdminMeResponse(admin_user=admin_user, permissions=permissions, env=env)


__all__ = ["router"]

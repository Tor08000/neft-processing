from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.admin_rbac import extract_admin_roles
from app.config import settings
from app.services.admin_portal_access import build_admin_permissions, primary_admin_level, resolve_admin_levels


class AdminPermission(BaseModel):
    read: bool
    operate: bool = False
    approve: bool = False
    override: bool = False
    manage: bool = False
    write: bool = False


class AdminPermissions(BaseModel):
    access: AdminPermission
    ops: AdminPermission
    runtime: AdminPermission
    finance: AdminPermission
    revenue: AdminPermission
    cases: AdminPermission
    commercial: AdminPermission
    crm: AdminPermission
    marketplace: AdminPermission
    legal: AdminPermission
    onboarding: AdminPermission
    audit: AdminPermission


class AdminEnv(BaseModel):
    name: str
    build: str
    region: str


class AdminAuditContext(BaseModel):
    require_reason: bool
    require_correlation_id: bool


class AdminUser(BaseModel):
    id: str
    email: str | None
    roles: list[str]
    issuer: str | None


class AdminMeResponse(BaseModel):
    admin_user: AdminUser
    roles: list[str]
    primary_role_level: str
    role_levels: list[str]
    permissions: AdminPermissions
    env: AdminEnv
    environment: AdminEnv
    read_only: bool
    audit_context: AdminAuditContext


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
    payload = build_admin_permissions(roles)
    return AdminPermissions.model_validate(payload)


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(token: dict = Depends(require_admin_user)) -> AdminMeResponse:
    roles = extract_admin_roles(token)
    user_id = token.get("user_id") or token.get("sub") or token.get("uid") or "unknown"
    email = token.get("email") or token.get("sub") or token.get("user_id") or token.get("uid")
    admin_user = AdminUser(
        id=str(user_id),
        email=email,
        roles=roles,
        issuer=token.get("iss"),
    )
    permissions = _build_permissions(roles)
    role_levels = resolve_admin_levels(roles)
    env = AdminEnv(
        name=_normalize_env_name(os.getenv("NEFT_ENV", "dev")),
        build=os.getenv("GIT_SHA", os.getenv("BUILD_SHA", "unknown")),
        region=os.getenv("NEFT_REGION", "local"),
    )
    audit_context = AdminAuditContext(
        require_reason=settings.AUDIT_REQUIRE_REASON,
        require_correlation_id=settings.AUDIT_REQUIRE_CORRELATION_ID,
    )
    return AdminMeResponse(
        admin_user=admin_user,
        roles=roles,
        primary_role_level=primary_admin_level(roles),
        role_levels=role_levels,
        permissions=permissions,
        env=env,
        environment=env,
        read_only=settings.ADMIN_READ_ONLY,
        audit_context=audit_context,
    )


__all__ = ["router"]

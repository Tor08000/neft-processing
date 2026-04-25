from __future__ import annotations

from typing import Any

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.db import get_conn
from app.lib.core_api import emit_admin_user_audit_via_core_api
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.security import decode_access_token, hash_password, security_scheme

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])
ADMIN_MANAGE_ROLES = {
    "PLATFORM_ADMIN",
    "ADMIN",
    "SUPERADMIN",
    "NEFT_ADMIN",
    "NEFT_SUPERADMIN",
}


def _user_state(*, row: dict[str, Any], roles: list[str]) -> dict[str, Any]:
    return {
        "email": row["email"],
        "full_name": row.get("full_name"),
        "is_active": bool(row["is_active"]),
        "roles": roles,
    }


def _admin_tenant_id(admin: dict[str, Any]) -> str:
    tenant_id = admin.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_required")
    return str(tenant_id)


async def _require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_access_token(credentials.credentials)
    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = payload.get("role")
    normalized_roles = {str(item).strip().upper() for item in [*roles, role] if item}
    if not normalized_roles.intersection(ADMIN_MANAGE_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return payload


async def _fetch_roles_with_cursor(cur, user_id: str) -> list[str]:
    await cur.execute(
        "SELECT role_code FROM user_roles WHERE user_id = %s ORDER BY role_code",
        (user_id,),
    )
    rows = await cur.fetchall()
    return [row["role_code"] for row in rows]


@router.get("", response_model=list[AdminUserResponse])
async def list_users(_admin=Depends(_require_admin)) -> list[AdminUserResponse]:
    async with get_conn() as (_conn, cur):
        await cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.is_active, u.created_at,
                   COALESCE(array_agg(ur.role_code ORDER BY ur.role_code), ARRAY[]::text[]) AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            GROUP BY u.id, u.email, u.full_name, u.is_active, u.created_at
            ORDER BY u.created_at DESC
            """
        )
        rows = await cur.fetchall()
    return [AdminUserResponse(**row) for row in rows]


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreateRequest,
    request: Request,
    _admin=Depends(_require_admin),
) -> AdminUserResponse:
    tenant_id = _admin_tenant_id(_admin)
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id FROM users WHERE tenant_id = %s AND lower(email) = lower(%s) LIMIT 1",
            (tenant_id, payload.email),
        )
        existing = await cur.fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

        password_hash = hash_password(payload.password)
        new_user_id = str(uuid4())
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, full_name, password_hash, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id, email, full_name, is_active, created_at
            """,
            (new_user_id, tenant_id, payload.email, payload.full_name, password_hash),
        )
        row = await cur.fetchone()
        user_id = row["id"]

        for role in payload.roles:
            await cur.execute(
                "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, role),
            )

        admin_bearer_token = request.headers.get("Authorization")
        if not admin_bearer_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
        await emit_admin_user_audit_via_core_api(
            admin_bearer_token=admin_bearer_token,
            action="create",
            user_id=str(user_id),
            before=None,
            after=_user_state(row=row, roles=payload.roles),
            reason=payload.reason,
            correlation_id=payload.correlation_id,
            request_id=request.headers.get("x-request-id"),
            trace_id=request.headers.get("x-trace-id"),
        )
        await conn.commit()

    return AdminUserResponse(**row, roles=payload.roles)


@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    _admin=Depends(_require_admin),
) -> AdminUserResponse:
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id, email, full_name, is_active, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
        before_roles = await _fetch_roles_with_cursor(cur, user_id)
        before_state = _user_state(row=existing, roles=before_roles)

        updates = []
        params: list[Any] = []
        if payload.full_name is not None:
            updates.append("full_name = %s")
            params.append(payload.full_name)
        if payload.is_active is not None:
            updates.append("is_active = %s")
            params.append(payload.is_active)

        if updates:
            set_clause = ", ".join(updates)
            await cur.execute(
                f"UPDATE users SET {set_clause} WHERE id = %s",
                (*params, user_id),
            )

        if payload.roles is not None:
            await cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            for role in payload.roles:
                await cur.execute(
                    "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user_id, role),
                )

        await cur.execute(
            "SELECT id, email, full_name, is_active, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        updated_row = await cur.fetchone()

        resolved_roles = payload.roles if payload.roles is not None else before_roles
        admin_bearer_token = request.headers.get("Authorization")
        if not admin_bearer_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
        await emit_admin_user_audit_via_core_api(
            admin_bearer_token=admin_bearer_token,
            action="update",
            user_id=user_id,
            before=before_state,
            after=_user_state(row=updated_row, roles=resolved_roles),
            reason=payload.reason,
            correlation_id=payload.correlation_id,
            request_id=request.headers.get("x-request-id"),
            trace_id=request.headers.get("x-trace-id"),
        )
        await conn.commit()

    return AdminUserResponse(**updated_row, roles=resolved_roles)

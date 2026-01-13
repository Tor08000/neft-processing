from __future__ import annotations

from typing import Any

from uuid import uuid4
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.db import get_conn
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.security import decode_access_token, hash_password, security_scheme

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


async def _require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_access_token(credentials.credentials)
    roles = payload.get("roles") or []
    if "PLATFORM_ADMIN" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return payload


async def _fetch_roles(user_id: str) -> list[str]:
    async with get_conn() as (_conn, cur):
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
    payload: AdminUserCreateRequest, _admin=Depends(_require_admin)
) -> AdminUserResponse:
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s) LIMIT 1",
            (payload.email,),
        )
        existing = await cur.fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_exists")

        password_hash = hash_password(payload.password)
        new_user_id = str(uuid4())
        await cur.execute(
            """
            INSERT INTO users (id, email, full_name, password_hash, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            RETURNING id, email, full_name, is_active, created_at
            """,
            (new_user_id, payload.email, payload.full_name, password_hash),
        )
        row = await cur.fetchone()
        user_id = row["id"]

        for role in payload.roles:
            await cur.execute(
                "INSERT INTO user_roles (user_id, role_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, role),
            )

        await conn.commit()

    roles = await _fetch_roles(str(user_id))
    return AdminUserResponse(**row, roles=roles)


@router.patch("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: str, payload: AdminUserUpdateRequest, _admin=Depends(_require_admin)
) -> AdminUserResponse:
    async with get_conn() as (conn, cur):
        await cur.execute(
            "SELECT id, email, full_name, is_active, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

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
        await conn.commit()

    roles = await _fetch_roles(user_id)
    return AdminUserResponse(**updated_row, roles=roles)

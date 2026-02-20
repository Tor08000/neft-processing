from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID, uuid4

from app.db import get_conn
from app.security import hash_password

logger = logging.getLogger(__name__)

DEFAULT_TENANT_CODE = "neft"
DEFAULT_TENANT_NAME = "NEFT Platform"

def _env_or_default(key: str, default: str, *, fallback_keys: Iterable[str] = ()) -> str:
    for candidate in (key, *fallback_keys):
        value = os.getenv(candidate)
        if value is not None and value != "":
            return value
    return default


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required env: {key}")
    return value


def _safe_uuid(value: str | None) -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        return uuid4()


def _parse_roles(raw_value: str | None, default: list[str]) -> list[str]:
    if raw_value is None or raw_value.strip() == "":
        return default
    return [role.strip() for role in raw_value.split(",") if role.strip()]


def _parse_uuid(raw_value: str | None) -> UUID | None:
    if raw_value is None or str(raw_value).strip() == "":
        return None
    try:
        return UUID(str(raw_value).strip())
    except Exception as exc:
        raise ValueError(f"Invalid tenant UUID value: {raw_value}") from exc


async def resolve_default_tenant_id(cur) -> UUID:  # noqa: ANN001
    await cur.execute("SELECT to_regclass('public.tenants') AS reg")
    tenant_table = await cur.fetchone()
    if not tenant_table or not tenant_table.get("reg"):
        raise RuntimeError("auth bootstrap requires public.tenants table when users.tenant_id is NOT NULL")

    requested_tenant_id = _parse_uuid(
        _env_or_default(
            "AUTH_DEFAULT_TENANT_ID",
            "",
            fallback_keys=("NEFT_TENANT_ID", "TENANT_ID"),
        )
    )
    if requested_tenant_id is not None:
        await cur.execute("SELECT id FROM tenants WHERE id = %s LIMIT 1", (requested_tenant_id,))
        existing = await cur.fetchone()
        if not existing:
            raise RuntimeError(f"Configured default tenant id {requested_tenant_id} not found in tenants table")
        return requested_tenant_id

    tenant_code = _env_or_default("AUTH_DEFAULT_TENANT_CODE", DEFAULT_TENANT_CODE).strip().lower() or DEFAULT_TENANT_CODE
    tenant_name = _env_or_default("AUTH_DEFAULT_TENANT_NAME", DEFAULT_TENANT_NAME).strip() or DEFAULT_TENANT_NAME
    await cur.execute(
        """
        INSERT INTO tenants (code, name)
        VALUES (%s, %s)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (tenant_code, tenant_name),
    )
    row = await cur.fetchone()
    if not row or not row.get("id"):
        raise RuntimeError(f"Unable to resolve default tenant for code={tenant_code}")
    return UUID(str(row["id"]))


@dataclass(frozen=True)
class DemoUser:
    email: str
    username: str | None
    password: str
    full_name: str | None
    roles: list[str]
    preferred_id: UUID | None = None


def get_demo_users() -> list[DemoUser]:
    admin_email = _require_env("NEFT_BOOTSTRAP_ADMIN_EMAIL")
    admin_username = _env_or_default("NEFT_BOOTSTRAP_ADMIN_USERNAME", _env_or_default("ADMIN_USERNAME", "admin"))
    admin_password = _require_env("NEFT_BOOTSTRAP_ADMIN_PASSWORD")
    admin_full_name = _env_or_default(
        "NEFT_BOOTSTRAP_ADMIN_FULL_NAME",
        _env_or_default(
            "ADMIN_FULL_NAME",
            _env_or_default("NEFT_DEMO_ADMIN_FULL_NAME", "Platform Admin", fallback_keys=("DEMO_ADMIN_FULL_NAME",)),
        ),
    )
    admin_roles = _parse_roles(
        _env_or_default(
            "NEFT_BOOTSTRAP_ADMIN_ROLES",
            _env_or_default("ADMIN_ROLES", "ADMIN,PLATFORM_ADMIN,SUPERADMIN"),
        ),
        ["PLATFORM_ADMIN"],
    )

    client_email = _env_or_default("NEFT_BOOTSTRAP_CLIENT_EMAIL", "client@neft.local")
    client_password = _env_or_default("NEFT_BOOTSTRAP_CLIENT_PASSWORD", "client123")
    client_full_name = _env_or_default(
        "NEFT_BOOTSTRAP_CLIENT_FULL_NAME",
        _env_or_default(
            "CLIENT_FULL_NAME",
            _env_or_default("NEFT_DEMO_CLIENT_FULL_NAME", "Demo Client", fallback_keys=("DEMO_CLIENT_FULL_NAME",)),
        ),
    )
    client_uuid = _env_or_default(
        "CLIENT_UUID",
        _env_or_default("NEFT_DEMO_CLIENT_UUID", "00000000-0000-0000-0000-000000000001", fallback_keys=("DEMO_CLIENT_UUID",)),
    )
    client_roles = _parse_roles(
        _env_or_default(
            "NEFT_BOOTSTRAP_CLIENT_ROLES",
            _env_or_default("CLIENT_ROLES", "CLIENT_OWNER"),
        ),
        ["CLIENT_OWNER"],
    )

    partner_email = _env_or_default("NEFT_BOOTSTRAP_PARTNER_EMAIL", "partner@neft.local")
    partner_password = _env_or_default("NEFT_BOOTSTRAP_PARTNER_PASSWORD", "partner123")
    partner_full_name = _env_or_default(
        "NEFT_BOOTSTRAP_PARTNER_FULL_NAME",
        _env_or_default("PARTNER_FULL_NAME", "Demo Partner"),
    )
    partner_roles = _parse_roles(
        _env_or_default(
            "NEFT_BOOTSTRAP_PARTNER_ROLES",
            _env_or_default("PARTNER_ROLES", "PARTNER_OWNER"),
        ),
        ["PARTNER_OWNER"],
    )

    return [
        DemoUser(
            email=admin_email,
            username=admin_username,
            password=admin_password,
            full_name=admin_full_name,
            roles=admin_roles,
        ),
        DemoUser(
            email=client_email,
            username=None,
            password=client_password,
            full_name=client_full_name,
            roles=client_roles,
            preferred_id=_safe_uuid(client_uuid),
        ),
        DemoUser(
            email=partner_email,
            username=None,
            password=partner_password,
            full_name=partner_full_name,
            roles=partner_roles,
        ),
    ]


async def ensure_user(
    demo_user: DemoUser,
    *,
    force_password: bool,
    sync_roles: bool,
    reset_password_once: bool = False,
    bootstrap_password_version: int = 0,
    tenant_id: UUID | None = None,
) -> str:
    normalized_email = demo_user.email.strip().lower()
    normalized_username = demo_user.username.strip().lower() if demo_user.username else None
    password_hash = hash_password(demo_user.password)
    demo_user_id = demo_user.preferred_id or uuid4()

    async with get_conn() as (conn, cur):
        resolved_tenant_id = tenant_id or await resolve_default_tenant_id(cur)
        await cur.execute(
            """
            SELECT id, email, username, full_name, password_hash, is_active, bootstrap_password_version, tenant_id
            FROM users
            WHERE lower(email) = lower(%s)
            """,
            (normalized_email,),
        )
        existing_user = await cur.fetchone()

        if existing_user and UUID(str(existing_user.get("tenant_id"))) != resolved_tenant_id:
            raise RuntimeError(
                f"User {normalized_email} exists in tenant {existing_user.get('tenant_id')} "
                f"but bootstrap requires tenant {resolved_tenant_id}"
            )

        password_reset = False
        roles_changed = False
        active_reset = False
        full_name_updated = False
        user_id = existing_user.get("id") if existing_user else demo_user_id

        target_version = max(int(bootstrap_password_version), 0)
        existing_version = 0
        if existing_user is not None:
            existing_version = int(existing_user.get("bootstrap_password_version") or 0)

        if not existing_user:
            insert_version = target_version if reset_password_once and force_password else 0
            await cur.execute(
                """
                INSERT INTO users (id, tenant_id, email, username, full_name, password_hash, is_active, bootstrap_password_version)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    user_id,
                    resolved_tenant_id,
                    normalized_email,
                    normalized_username,
                    demo_user.full_name,
                    password_hash,
                    insert_version,
                ),
            )
            password_reset = True
            full_name_updated = bool(demo_user.full_name)
            logger.info("seed user created: email=%s, roles=%s", normalized_email, demo_user.roles)
        else:
            if not existing_user.get("is_active", True):
                await cur.execute(
                    "UPDATE users SET is_active = TRUE WHERE id = %s",
                    (user_id,),
                )
                active_reset = True

            existing_hash = existing_user.get("password_hash")
            if force_password:
                should_reset = True
                if reset_password_once:
                    should_reset = existing_version < target_version
                if should_reset:
                    await cur.execute(
                        "UPDATE users SET password_hash = %s, bootstrap_password_version = %s WHERE id = %s",
                        (password_hash, target_version, user_id),
                    )
                    password_reset = True

            if normalized_username and normalized_username != (existing_user.get("username") or ""):
                await cur.execute(
                    "UPDATE users SET username = %s WHERE id = %s",
                    (normalized_username, user_id),
                )

            if demo_user.full_name and demo_user.full_name != existing_user.get("full_name"):
                await cur.execute(
                    "UPDATE users SET full_name = %s WHERE id = %s",
                    (demo_user.full_name, user_id),
                )
                full_name_updated = True

        await cur.execute(
            "SELECT role_code FROM user_roles WHERE user_id = %s",
            (user_id,),
        )
        existing_roles = {row["role_code"] for row in await cur.fetchall()}
        desired_roles = set(demo_user.roles)
        missing_roles = desired_roles - existing_roles
        extra_roles = existing_roles - desired_roles if sync_roles else set()

        for role in missing_roles:
            await cur.execute(
                """
                INSERT INTO user_roles (user_id, role_code)
                VALUES (%s, %s)
                ON CONFLICT (user_id, role_code) DO NOTHING
                """,
                (user_id, role),
            )

        if extra_roles:
            await cur.execute(
                "DELETE FROM user_roles WHERE user_id = %s AND role_code = ANY(%s)",
                (user_id, list(extra_roles)),
            )

        roles_changed = bool(missing_roles or extra_roles)

        await conn.commit()

        logger.info(
            "[bootstrap] %s password reset = %s",
            normalized_email,
            str(password_reset).lower(),
        )
        logger.info(
            "demo user sync: email=%s password_reset=%s roles_changed=%s active_reset=%s full_name_updated=%s",
            normalized_email,
            password_reset,
            roles_changed,
            active_reset,
            full_name_updated,
        )

        if not existing_user:
            return "created"

        if password_reset or roles_changed or active_reset or full_name_updated:
            return "updated"

        return "skipped"

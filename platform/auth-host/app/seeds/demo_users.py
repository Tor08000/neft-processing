from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID, uuid4

from app.db import get_conn
from app.security import hash_password

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class DemoUser:
    email: str
    password: str
    full_name: str | None
    roles: list[str]
    preferred_id: UUID | None = None


def get_demo_users() -> list[DemoUser]:
    admin_email = _require_env("NEFT_BOOTSTRAP_ADMIN_EMAIL")
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

    client_email = _require_env("NEFT_BOOTSTRAP_CLIENT_EMAIL")
    client_password = _require_env("NEFT_BOOTSTRAP_CLIENT_PASSWORD")
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

    partner_email = _require_env("NEFT_BOOTSTRAP_PARTNER_EMAIL")
    partner_password = _require_env("NEFT_BOOTSTRAP_PARTNER_PASSWORD")
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
            password=admin_password,
            full_name=admin_full_name,
            roles=admin_roles,
        ),
        DemoUser(
            email=client_email,
            password=client_password,
            full_name=client_full_name,
            roles=client_roles,
            preferred_id=_safe_uuid(client_uuid),
        ),
        DemoUser(
            email=partner_email,
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
) -> str:
    normalized_email = demo_user.email.strip().lower()
    password_hash = hash_password(demo_user.password)
    demo_user_id = demo_user.preferred_id or uuid4()

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, email, full_name, password_hash, is_active
            FROM users
            WHERE lower(email) = lower(%s)
            """,
            (normalized_email,),
        )
        existing_user = await cur.fetchone()

        password_reset = False
        roles_changed = False
        active_reset = False
        full_name_updated = False
        user_id = existing_user.get("id") if existing_user else demo_user_id

        if not existing_user:
            await cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                """,
                (user_id, normalized_email, demo_user.full_name, password_hash),
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
                await cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id),
                )
                password_reset = True

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

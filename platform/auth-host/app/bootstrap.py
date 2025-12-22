from __future__ import annotations

import logging
from uuid import UUID, uuid4

from app.db import get_conn, init_db
from app.security import hash_password, verify_password
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


async def seed_demo_client_account(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    try:
        await _ensure_demo_accounts(settings)
    except Exception:
        logger.warning("Demo bootstrap failed; continuing without demo users", exc_info=True)


async def _ensure_demo_accounts(settings: Settings) -> None:
    await init_db()

    await bootstrap_demo_client(settings=settings)
    await bootstrap_admin_account(settings=settings)


async def bootstrap_demo_client(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    await _ensure_demo_user(
        email=settings.demo_client_email.strip(),
        password=settings.demo_client_password,
        full_name=settings.demo_client_full_name,
        roles=["CLIENT_OWNER"],
        label="demo client",
        preferred_id=_safe_uuid(settings.demo_client_uuid),
    )


async def bootstrap_demo_admin(settings: Settings | None = None) -> None:
    await bootstrap_admin_account(settings=settings)


async def bootstrap_admin_account(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    email = (settings.bootstrap_admin_email or settings.demo_admin_email).strip()
    password = settings.bootstrap_admin_password or settings.demo_admin_password
    full_name = settings.bootstrap_admin_full_name or settings.demo_admin_full_name
    roles = settings.bootstrap_admin_roles or settings.demo_admin_roles
    await _ensure_demo_user(
        email=email,
        password=password,
        full_name=full_name,
        roles=roles,
        label="bootstrap admin",
    )


def _safe_uuid(value: str | None) -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        return uuid4()


async def _ensure_demo_user(
    *,
    email: str,
    password: str,
    full_name: str | None,
    roles: list[str],
    label: str,
    preferred_id: UUID | None = None,
) -> None:
    normalized_email = email.strip().lower()
    password_hash = hash_password(password)
    demo_user_id = preferred_id or uuid4()

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, email, password_hash, is_active FROM users WHERE lower(email) = lower(%s)
            """,
            (normalized_email,),
        )
        existing_user = await cur.fetchone()

        password_reset = False
        user_id = existing_user.get("id") if existing_user else demo_user_id

        if not existing_user:
            await cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (user_id, normalized_email, full_name, password_hash),
            )
            row = await cur.fetchone()
            user_id = row.get("id") if row else user_id
            password_reset = True
            logger.info("%s seeded: email=%s, user_id=%s, roles=%s", label, normalized_email, user_id, roles)
        else:
            if not existing_user.get("is_active", True):
                await cur.execute(
                    "UPDATE users SET is_active = TRUE WHERE id = %s",
                    (user_id,),
                )
            if not verify_password(password, existing_user.get("password_hash", "")):
                await cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id),
                )
                password_reset = True

        await cur.execute(
            "SELECT role FROM user_roles WHERE user_id = %s",
            (user_id,),
        )
        existing_roles = {row["role"] for row in await cur.fetchall()}
        missing_roles = [role for role in roles if role not in existing_roles]

        for role in missing_roles:
            await cur.execute(
                """
                INSERT INTO user_roles (user_id, role)
                VALUES (%s, %s)
                ON CONFLICT (user_id, role) DO NOTHING
                """,
                (user_id, role),
            )

        await conn.commit()

        if existing_user:
            logger.info(
                "%s already exists: email=%s, user_id=%s, updated_roles=%s, password_reset=%s",
                label,
                normalized_email,
                user_id,
                bool(missing_roles),
                password_reset,
            )

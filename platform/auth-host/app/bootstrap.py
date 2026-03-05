from __future__ import annotations

import logging
from uuid import UUID, uuid4

from app.db import get_conn
from app.security import hash_password, verify_password
from app.settings import Settings, get_settings
from app.seeds.demo_users import ensure_user, get_demo_users

logger = logging.getLogger(__name__)


def _is_dev_mode(settings: Settings) -> bool:
    app_env = (getattr(settings, "APP_ENV", "") or "").strip().lower()
    start_mode = (getattr(settings, "START_MODE", "") or "").strip().lower()
    return app_env in {"dev", "local", "development", "test"} or start_mode == "dev"


async def seed_demo_client_account(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    try:
        await _ensure_demo_accounts(settings)
    except Exception:
        logger.warning("Demo bootstrap failed; continuing without demo users", exc_info=True)


async def bootstrap_required_users(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.bootstrap_enabled:
        logger.info("auth bootstrap: disabled via NEFT_BOOTSTRAP_ENABLED")
        return

    if not _is_dev_mode(settings):
        logger.info("auth bootstrap: skipped because runtime mode is not dev")
        return

    demo_users = get_demo_users()
    force_password_reset = True
    for demo_user in demo_users:
        status = await ensure_user(
            demo_user,
            force_password=force_password_reset,
            sync_roles=True,
            reset_password_once=True,
            bootstrap_password_version=settings.bootstrap_password_version,
        )
        logger.info(
            "auth bootstrap: required user sync finished",
            extra={"email": demo_user.email, "status": status},
        )

    credential_labels = ("admin", "client", "partner")
    for label, demo_user in zip(credential_labels, demo_users, strict=False):
        login_hint = demo_user.username or demo_user.email
        logger.info(
            "auth bootstrap demo credentials: role=%s login=%s password=%s",
            label,
            login_hint,
            demo_user.password,
        )


async def _ensure_demo_accounts(settings: Settings) -> None:
    await bootstrap_demo_client(settings=settings)
    await bootstrap_admin_account_with_seed(
        settings=settings,
        force_password_reset=settings.demo_seed_force_password_reset,
        ensure_password=False,
    )


async def bootstrap_demo_client(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    await _ensure_demo_user(
        email=settings.demo_client_email.strip(),
        username=None,
        password=settings.demo_client_password,
        full_name=settings.demo_client_full_name,
        roles=["CLIENT_OWNER"],
        label="demo client",
        preferred_id=_safe_uuid(settings.demo_client_uuid),
        force_password_reset=settings.demo_seed_force_password_reset,
    )


async def bootstrap_demo_admin(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    await bootstrap_admin_account_with_seed(
        settings=settings,
        force_password_reset=settings.demo_seed_force_password_reset,
        ensure_password=False,
    )


async def bootstrap_admin_account(settings: Settings | None = None) -> None:
    await bootstrap_admin_account_with_seed(settings=settings)


async def bootstrap_admin_account_with_seed(
    settings: Settings | None = None,
    *,
    force_password_reset: bool = False,
    ensure_password: bool = True,
) -> None:
    settings = settings or get_settings()
    email = (settings.bootstrap_admin_email or settings.demo_admin_email).strip()
    password = settings.bootstrap_admin_password or settings.demo_admin_password
    full_name = settings.bootstrap_admin_full_name or settings.demo_admin_full_name
    roles = settings.bootstrap_admin_roles or settings.demo_admin_roles
    await _ensure_demo_user(
        email=email,
        username=(settings.bootstrap_admin_username or settings.demo_admin_username),
        password=password,
        full_name=full_name,
        roles=roles,
        label="bootstrap admin",
        force_password_reset=force_password_reset,
        ensure_password=ensure_password,
    )


async def bootstrap_admin(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.bootstrap_enabled:
        logger.info("auth bootstrap: disabled via NEFT_BOOTSTRAP_ENABLED")
        return

    email = (settings.bootstrap_admin_email or "").strip()
    password = settings.bootstrap_admin_password
    if not email or not password:
        logger.warning("auth bootstrap: missing credentials, skipping admin bootstrap")
        return

    status = await _ensure_demo_user(
        email=email,
        username=(settings.bootstrap_admin_username or settings.demo_admin_username),
        password=password,
        full_name=settings.bootstrap_admin_full_name,
        roles=settings.bootstrap_admin_roles,
        label="bootstrap admin",
        ensure_password=True,
    )
    logger.info(
        "auth bootstrap: admin seed finished",
        extra={"email": email, "roles": settings.bootstrap_admin_roles, "status": status},
    )


def _safe_uuid(value: str | None) -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        return uuid4()


async def _ensure_demo_user(
    *,
    email: str,
    username: str | None,
    password: str,
    full_name: str | None,
    roles: list[str],
    label: str,
    preferred_id: UUID | None = None,
    ensure_password: bool = False,
    force_password_reset: bool = False,
) -> str:
    normalized_email = email.strip().lower()
    normalized_username = username.strip().lower() if username else None
    password_hash = hash_password(password)
    demo_user_id = preferred_id or uuid4()

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, email, username, password_hash, is_active FROM users WHERE lower(email) = lower(%s)
            """,
            (normalized_email,),
        )
        existing_user = await cur.fetchone()

        password_reset = False
        user_id = existing_user.get("id") if existing_user else demo_user_id

        if not existing_user:
            await cur.execute(
                """
                INSERT INTO users (id, email, username, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (user_id, normalized_email, normalized_username, full_name, password_hash),
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
            if normalized_username and normalized_username != (existing_user.get("username") or ""):
                await cur.execute(
                    "UPDATE users SET username = %s WHERE id = %s",
                    (normalized_username, user_id),
                )

            existing_hash = existing_user.get("password_hash")
            if force_password_reset:
                await cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id),
                )
                password_reset = True
            elif ensure_password and (not existing_hash or not verify_password(password, existing_hash)):
                await cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, user_id),
                )
                password_reset = True

        await cur.execute(
            "SELECT role_code FROM user_roles WHERE user_id = %s",
            (user_id,),
        )
        existing_roles = {row["role_code"] for row in await cur.fetchall()}
        missing_roles = [role for role in roles if role not in existing_roles]

        for role in missing_roles:
            await cur.execute(
                """
                INSERT INTO user_roles (user_id, role_code)
                VALUES (%s, %s)
                ON CONFLICT (user_id, role_code) DO NOTHING
                """,
                (user_id, role),
            )

        await conn.commit()

        status = "noop"
        if existing_user:
            logger.info(
                "%s already exists: email=%s, user_id=%s, updated_roles=%s, password_reset=%s",
                label,
                normalized_email,
                user_id,
                bool(missing_roles),
                password_reset,
            )
            status = "updated" if missing_roles or password_reset or not existing_user.get("is_active", True) else "noop"
        else:
            logger.info("%s seeded: email=%s, user_id=%s, roles=%s", label, normalized_email, user_id, roles)
            status = "created"
        return status

from __future__ import annotations

import logging
import os
from uuid import uuid4

from app.db import get_conn, init_db
from app.demo import DEMO_CLIENT_EMAIL, DEMO_CLIENT_FULL_NAME, DEMO_CLIENT_PASSWORD
from app.security import hash_password

logger = logging.getLogger(__name__)


async def seed_demo_client_account() -> None:
    try:
        await _ensure_demo_accounts()
    except Exception:
        logger.warning("Demo client bootstrap failed; continuing without demo user", exc_info=True)


async def _ensure_demo_accounts() -> None:
    await init_db()

    await _ensure_demo_user(
        email=os.getenv("NEFT_DEMO_CLIENT_EMAIL", DEMO_CLIENT_EMAIL).strip(),
        password=os.getenv("NEFT_DEMO_CLIENT_PASSWORD", DEMO_CLIENT_PASSWORD),
        full_name=os.getenv("NEFT_DEMO_CLIENT_FULL_NAME", DEMO_CLIENT_FULL_NAME),
        roles=["CLIENT_OWNER"],
        label="demo client",
    )

    await _ensure_demo_user(
        email=os.getenv("NEFT_DEMO_ADMIN_EMAIL", "admin@example.com").strip(),
        password=os.getenv("NEFT_DEMO_ADMIN_PASSWORD", "admin"),
        full_name=os.getenv("NEFT_DEMO_ADMIN_FULL_NAME", "Platform Admin"),
        roles=["PLATFORM_ADMIN"],
        label="demo admin",
    )


async def _ensure_demo_user(
    *, email: str, password: str, full_name: str | None, roles: list[str], label: str
) -> None:
    password_hash = hash_password(password)
    demo_user_id = uuid4()

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, email FROM users WHERE lower(email) = lower(%s)
            """,
            (email,),
        )
        existing_user = await cur.fetchone()

        user_id = existing_user.get("id") if existing_user else demo_user_id

        if not existing_user:
            await cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (user_id, email, full_name, password_hash),
            )
            row = await cur.fetchone()
            user_id_value = row.get("id") if row else None
            logger.info("%s seeded: email=%s, user_id=%s", label, email, user_id_value)
        else:
            logger.info(
                "%s already exists: email=%s, user_id=%s",
                label,
                email,
                existing_user.get("id"),
            )

        for role in roles:
            await cur.execute(
                """
                INSERT INTO user_roles (user_id, role)
                VALUES (%s, %s)
                ON CONFLICT (user_id, role) DO NOTHING
                """,
                (user_id, role),
            )

        await conn.commit()

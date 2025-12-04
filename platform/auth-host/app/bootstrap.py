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
        await _ensure_demo_client_account()
    except Exception:
        logger.warning("Demo client bootstrap failed; continuing without demo user", exc_info=True)


async def _ensure_demo_client_account() -> None:
    await init_db()

    demo_email = os.getenv("NEFT_DEMO_CLIENT_EMAIL", DEMO_CLIENT_EMAIL).strip()
    demo_password = os.getenv("NEFT_DEMO_CLIENT_PASSWORD", DEMO_CLIENT_PASSWORD)
    demo_full_name = os.getenv("NEFT_DEMO_CLIENT_FULL_NAME", DEMO_CLIENT_FULL_NAME)

    password_hash = hash_password(demo_password)
    demo_user_id = uuid4()

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            SELECT id, email FROM users WHERE lower(email) = lower(%s)
            """,
            (demo_email,),
        )
        existing_user = await cur.fetchone()

        if not existing_user:
            await cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
                """,
                (demo_user_id, demo_email, demo_full_name, password_hash),
            )
            row = await cur.fetchone()
            user_id_value = row.get("id") if row else None
            logger.info(
                "demo client seeded: email=%s, user_id=%s", demo_email, user_id_value
            )
        else:
            logger.info(
                "demo client already exists: email=%s, user_id=%s",
                demo_email,
                existing_user.get("id"),
            )

        await conn.commit()

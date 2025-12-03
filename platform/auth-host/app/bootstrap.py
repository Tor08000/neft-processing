from __future__ import annotations

import logging
from uuid import UUID

from app.db import get_conn, init_db
from app.demo import (
    DEMO_CLIENT_EMAIL,
    DEMO_CLIENT_FULL_NAME,
    DEMO_CLIENT_ID,
    DEMO_CLIENT_PASSWORD,
    DEMO_CLIENT_UUID,
)
from app.security import hash_password

logger = logging.getLogger(__name__)


async def seed_demo_client_account() -> None:
    try:
        await _ensure_demo_client_account()
    except Exception:
        logger.warning("Demo client bootstrap failed; continuing without demo user", exc_info=True)


async def _ensure_demo_client_account() -> None:
    await init_db()

    password_hash = hash_password(DEMO_CLIENT_PASSWORD)
    demo_client_id = UUID(DEMO_CLIENT_UUID)

    async with get_conn() as (conn, cur):
        await cur.execute(
            """
            INSERT INTO clients (id, tenant_id, name, email, full_name, status)
            VALUES (%s, 1, %s, %s, %s, 'ACTIVE')
            ON CONFLICT (id) DO UPDATE
            SET email = EXCLUDED.email,
                full_name = EXCLUDED.full_name,
                name = EXCLUDED.name,
                status = EXCLUDED.status
            """,
            (
                demo_client_id,
                DEMO_CLIENT_FULL_NAME,
                DEMO_CLIENT_EMAIL,
                DEMO_CLIENT_FULL_NAME,
            ),
        )

        await cur.execute(
            """
            INSERT INTO users (email, full_name, password_hash, is_active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE
            SET full_name = EXCLUDED.full_name,
                password_hash = EXCLUDED.password_hash,
                is_active = TRUE
            RETURNING id
            """,
            (DEMO_CLIENT_EMAIL, DEMO_CLIENT_FULL_NAME, password_hash),
        )

        await conn.commit()
        logger.info("Demo client account ensured", extra={"email": DEMO_CLIENT_EMAIL, "id": DEMO_CLIENT_ID})

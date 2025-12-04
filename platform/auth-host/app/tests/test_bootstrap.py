from __future__ import annotations

import pytest
import psycopg

from app import db
from app.bootstrap import seed_demo_client_account


@pytest.mark.anyio
async def test_init_db_and_bootstrap_creates_demo_user():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    async with conn.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS users")
        await conn.commit()
    await conn.close()

    await db.init_db()
    await seed_demo_client_account()

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email, is_active FROM users WHERE lower(email) = lower(%s)",
            ("client@neft.local",),
        )
        row = await cur.fetchone()

    assert row is not None
    assert row["email"].lower() == "client@neft.local"
    assert row["is_active"] is True

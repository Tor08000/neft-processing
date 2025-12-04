from __future__ import annotations

import pytest
import psycopg
import httpx

from app import bootstrap, db
from app.demo import DEMO_CLIENT_EMAIL, DEMO_CLIENT_PASSWORD
from app.main import app


@pytest.mark.anyio
async def test_demo_login_against_real_db():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    await db.init_db()
    await bootstrap.seed_demo_client_account()

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email FROM users WHERE lower(email) = lower(%s) LIMIT 1",
            (DEMO_CLIENT_EMAIL,),
        )
        assert await cur.fetchone()

        await cur.execute(
            "SELECT email FROM clients WHERE lower(email) = lower(%s) LIMIT 1",
            (DEMO_CLIENT_EMAIL,),
        )
        assert await cur.fetchone()

    transport = httpx.ASGITransport(app=app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_CLIENT_EMAIL, "password": DEMO_CLIENT_PASSWORD},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["email"] == DEMO_CLIENT_EMAIL
    assert data["subject_type"] == "client_user"
    assert data["client_id"]

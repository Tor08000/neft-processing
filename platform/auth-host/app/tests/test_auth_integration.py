from __future__ import annotations

import pytest
import psycopg
import httpx

from app import bootstrap, db
from app.demo import DEMO_CLIENT_EMAIL, DEMO_CLIENT_PASSWORD
from app.main import app
from app.settings import Settings


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
    assert data["subject_type"] == "user"


@pytest.mark.anyio
async def test_demo_admin_login_and_wrong_password():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    settings = Settings()

    await db.init_db()
    await bootstrap.bootstrap_demo_admin(settings)

    transport = httpx.ASGITransport(app=app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok_response = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.demo_admin_email, "password": settings.demo_admin_password},
        )

        wrong_password_response = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.demo_admin_email, "password": "definitely-wrong"},
        )

    assert ok_response.status_code == 200
    ok_data = ok_response.json()
    assert ok_data["email"] == settings.demo_admin_email
    assert "ADMIN" in ok_data.get("roles", [])

    assert wrong_password_response.status_code == 401

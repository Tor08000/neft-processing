from __future__ import annotations

from uuid import uuid4

import httpx
import psycopg
import pytest

from app import db
from app.main import app
from app.tests.migration_helpers import run_auth_migrations


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _ensure_core_signup_tables() -> None:
    conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    try:
        async with conn.cursor() as cur:
            await cur.execute("CREATE SCHEMA IF NOT EXISTS processing_core")
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_core.clients (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_core.client_onboarding (
                    client_id UUID NOT NULL,
                    owner_user_id UUID NOT NULL,
                    step TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            await conn.commit()
    finally:
        await conn.close()


@pytest.mark.anyio
async def test_signup_success_returns_non_503_and_user_data():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    await _ensure_core_signup_tables()

    email = f"signup-{uuid4().hex[:10]}@example.com"
    transport = httpx.ASGITransport(app=app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "Passw0rd!123", "full_name": "Signup User"},
            headers={"host": "neft.local"},
        )

    assert response.status_code in {200, 201}
    assert response.status_code != 503
    data = response.json()
    assert data["email"] == email
    assert data["id"]
    assert data["client_id"]


@pytest.mark.anyio
async def test_signup_regression_path_reaches_core_client_creation_without_monkeypatch():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    await _ensure_core_signup_tables()

    email = f"signup-reg-{uuid4().hex[:10]}@example.com"
    transport = httpx.ASGITransport(app=app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "Passw0rd!123", "full_name": "Regression User"},
            headers={"host": "neft.local"},
        )

    assert response.status_code != 503
    payload = response.json()
    user_id = payload["id"]
    client_id = payload["client_id"]

    async with db.get_conn() as (_conn, cur):
        await cur.execute("SELECT client_id FROM user_clients WHERE user_id=%s", (user_id,))
        link_row = await cur.fetchone()

    core_conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    try:
        async with core_conn.cursor() as cur:
            await cur.execute("SELECT id, email FROM processing_core.clients WHERE id=%s", (client_id,))
            client_row = await cur.fetchone()
    finally:
        await core_conn.close()

    assert link_row is not None
    assert str(link_row["client_id"]) == client_id
    assert client_row is not None
    assert client_row["email"] == email

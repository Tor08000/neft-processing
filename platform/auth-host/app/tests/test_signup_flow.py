from __future__ import annotations

from uuid import uuid4

import httpx
import psycopg
import pytest

from app import db
from app.api.routes import auth
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
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_core.client_users (
                    id UUID PRIMARY KEY,
                    client_id UUID NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_core.client_user_roles (
                    id UUID PRIMARY KEY,
                    client_id UUID NOT NULL,
                    user_id TEXT NOT NULL,
                    roles JSONB NOT NULL
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
    transport = httpx.ASGITransport(app=app)
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
    transport = httpx.ASGITransport(app=app)
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
            await cur.execute(
                "SELECT user_id, status FROM processing_core.client_users WHERE client_id=%s AND user_id=%s",
                (client_id, user_id),
            )
            client_user_row = await cur.fetchone()
            await cur.execute(
                "SELECT roles FROM processing_core.client_user_roles WHERE client_id=%s AND user_id=%s",
                (client_id, user_id),
            )
            client_user_roles_row = await cur.fetchone()
    finally:
        await core_conn.close()

    assert link_row is not None
    assert str(link_row["client_id"]) == client_id
    assert client_row is not None
    assert client_row["email"] == email
    assert client_user_row is not None
    assert str(client_user_row["user_id"]) == user_id
    assert str(client_user_row["status"]).upper() == "ACTIVE"
    assert client_user_roles_row is not None
    assert "CLIENT_OWNER" in list(client_user_roles_row["roles"] or [])


@pytest.mark.anyio
async def test_signup_token_remains_valid_for_me_when_session_persistence_is_skipped(monkeypatch: pytest.MonkeyPatch):
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    await _ensure_core_signup_tables()

    async def fail_create_session(**_kwargs):
        raise RuntimeError("session store unavailable")

    monkeypatch.setattr(auth, "_create_session", fail_create_session)

    email = f"signup-me-{uuid4().hex[:10]}@example.com"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "Passw0rd!123", "full_name": "Signup Me User"},
            headers={"host": "neft.local"},
        )

        assert signup.status_code in {200, 201}
        token = signup.json()["access_token"]
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}", "X-Portal": "client"},
        )

    assert me.status_code == 200
    payload = me.json()
    assert payload["email"] == email
    assert payload["subject_type"] == "client_user"
    assert payload["client_id"]

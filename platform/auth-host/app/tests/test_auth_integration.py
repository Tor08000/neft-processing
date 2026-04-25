from __future__ import annotations

import pytest
import psycopg
import httpx

from app import bootstrap, db
from app.demo import DEMO_CLIENT_EMAIL, DEMO_CLIENT_PASSWORD
from app.main import app
from app.security import hash_password
from app.settings import Settings
from app.tests.migration_helpers import run_auth_migrations


async def _reset_auth_tables(connection: psycopg.AsyncConnection) -> None:
    async with connection.cursor() as cur:
        await cur.execute(
            """
            DROP TABLE IF EXISTS
                auth_sessions,
                sso_exchange_codes,
                user_identities,
                refresh_tokens,
                oauth_identities,
                user_clients,
                user_roles,
                users
            CASCADE
            """
        )
        await cur.execute("DROP TABLE IF EXISTS public.alembic_version")
        await cur.execute("DROP TABLE IF EXISTS processing_auth.alembic_version_auth")
        await connection.commit()


@pytest.mark.anyio
async def test_demo_login_against_real_db():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    await bootstrap.seed_demo_client_account()

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email FROM users WHERE lower(email) = lower(%s) LIMIT 1",
            (DEMO_CLIENT_EMAIL,),
        )
        assert await cur.fetchone()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_CLIENT_EMAIL, "password": DEMO_CLIENT_PASSWORD, "portal": "client"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["email"] == DEMO_CLIENT_EMAIL
    assert data["subject_type"] == "client_user"


@pytest.mark.anyio
async def test_bootstrap_required_users_seeds_demo_admin_and_allows_login():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    await _reset_auth_tables(conn)
    await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    settings = Settings()
    await bootstrap.bootstrap_required_users(settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email, is_active FROM users WHERE lower(email)=lower(%s) LIMIT 1",
            ("admin@neft.local",),
        )
        admin_row = await cur.fetchone()

        await cur.execute(
            "SELECT role_code FROM user_roles ur JOIN users u ON u.id = ur.user_id WHERE lower(u.email)=lower(%s)",
            ("admin@neft.local",),
        )
        admin_roles = {r["role_code"] for r in await cur.fetchall()}

    assert admin_row is not None
    assert admin_row["is_active"] is True
    assert {"ADMIN", "PLATFORM_ADMIN"}.issubset(admin_roles)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@neft.local", "password": "Neft123!", "portal": "admin"},
        )

    assert response.status_code == 200




@pytest.mark.anyio
async def test_bootstrap_required_users_resets_existing_demo_password_in_dev_mode():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)

    settings = Settings(APP_ENV="dev")
    await bootstrap.bootstrap_required_users(settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "UPDATE users SET password_hash = %s WHERE lower(email)=lower(%s)",
            (hash_password("definitely-wrong"), "client@neft.local"),
        )

    await bootstrap.bootstrap_required_users(settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "client@neft.local", "password": "Neft123!", "portal": "client"},
        )

    assert response.status_code == 200

@pytest.mark.anyio
async def test_bootstrap_required_users_resets_partner_demo_password_in_dev_mode():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    run_auth_migrations(db.DSN_ASYNC)

    settings = Settings(APP_ENV="dev")
    await bootstrap.bootstrap_required_users(settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "UPDATE users SET password_hash = %s WHERE lower(email)=lower(%s)",
            (hash_password("definitely-wrong"), "partner@neft.local"),
        )

    await bootstrap.bootstrap_required_users(settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "partner@neft.local", "password": "Partner123!", "portal": "partner"},
        )

    assert response.status_code == 200


@pytest.mark.anyio
async def test_demo_admin_login_and_wrong_password():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")
    else:
        await conn.close()

    settings = Settings()

    run_auth_migrations(db.DSN_ASYNC)
    await bootstrap.bootstrap_demo_admin(settings)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok_response = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.demo_admin_email, "password": settings.demo_admin_password, "portal": "admin"},
        )

        wrong_password_response = await client.post(
            "/api/v1/auth/login",
            json={"email": settings.demo_admin_email, "password": "definitely-wrong", "portal": "admin"},
        )

    assert ok_response.status_code == 200
    ok_data = ok_response.json()
    assert ok_data["email"] == settings.demo_admin_email
    assert "ADMIN" in ok_data.get("roles", [])

    assert wrong_password_response.status_code == 401

from __future__ import annotations

import pytest
import psycopg

from app import db
from app.bootstrap import bootstrap_demo_admin, seed_demo_client_account
from app.security import verify_password
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
async def test_migrations_and_bootstrap_creates_demo_user():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    await _reset_auth_tables(conn)
    await conn.close()

    run_auth_migrations(db.DSN_ASYNC)
    await seed_demo_client_account(Settings())

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email, is_active FROM users WHERE lower(email) = lower(%s)",
            ("client@neft.local",),
        )
        row = await cur.fetchone()

        await cur.execute(
            "SELECT role_code FROM user_roles ur JOIN users u ON ur.user_id = u.id WHERE lower(u.email)=lower(%s)",
            ("client@neft.local",),
        )
        client_roles = [r["role_code"] for r in await cur.fetchall()]

        await cur.execute(
            "SELECT role_code FROM user_roles ur JOIN users u ON ur.user_id = u.id WHERE lower(u.email)=lower(%s)",
            ("admin@neft.local",),
        )
        admin_roles = [r["role_code"] for r in await cur.fetchall()]

    assert row is not None
    assert row["email"].lower() == "client@neft.local"
    assert row["is_active"] is True
    assert "CLIENT_OWNER" in client_roles
    assert "ADMIN" in admin_roles


@pytest.mark.anyio
async def test_bootstrap_admin_is_idempotent_and_updates_password():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    await _reset_auth_tables(conn)
    await conn.close()

    run_auth_migrations(db.DSN_ASYNC)

    initial_settings = Settings(
        bootstrap_admin_email="admin@neft.local",
        bootstrap_admin_password="Neft123!",
        bootstrap_admin_roles=["ADMIN", "SUPERADMIN"],
        demo_admin_email="admin@neft.local",
        demo_admin_password="Neft123!",
        demo_admin_roles=["ADMIN", "SUPERADMIN"],
    )
    await bootstrap_demo_admin(initial_settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT id, password_hash, is_active FROM users WHERE lower(email)=lower(%s)",
            (initial_settings.demo_admin_email,),
        )
        first_row = await cur.fetchone()
        first_hash = first_row["password_hash"]

        await cur.execute(
            "SELECT role_code FROM user_roles WHERE user_id = %s",
            (first_row["id"],),
        )
        roles_after_first = [r["role_code"] for r in await cur.fetchall()]

    updated_settings = Settings(
        bootstrap_admin_email="admin@neft.local",
        bootstrap_admin_password="Neft456!",
        bootstrap_admin_roles=["ADMIN", "SUPERADMIN"],
        demo_admin_email="admin@neft.local",
        demo_admin_password="Neft456!",
        demo_admin_roles=["ADMIN", "SUPERADMIN"],
    )
    await bootstrap_demo_admin(updated_settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT COUNT(*) FROM users WHERE lower(email)=lower(%s)",
            (updated_settings.demo_admin_email,),
        )
        user_count = (await cur.fetchone())["count"]

        await cur.execute(
            "SELECT password_hash FROM users WHERE lower(email)=lower(%s)",
            (updated_settings.demo_admin_email,),
        )
        updated_row = await cur.fetchone()

        await cur.execute(
            "SELECT role_code FROM user_roles WHERE lower(user_id::text)=lower(%s)",
            (str(first_row["id"]),),
        )
        roles_after_second = [r["role_code"] for r in await cur.fetchall()]

    assert user_count == 1
    assert verify_password("Neft456!", updated_row["password_hash"])
    assert updated_row["password_hash"] != first_hash
    expected_roles = sorted(set(updated_settings.bootstrap_admin_roles))
    assert sorted(set(roles_after_first)) == sorted(set(roles_after_second)) == expected_roles


@pytest.mark.anyio
async def test_bootstrap_admin_reuses_legacy_username_and_normalizes_email():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    await _reset_auth_tables(conn)
    await conn.close()

    run_auth_migrations(db.DSN_ASYNC)

    legacy_settings = Settings(
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_username="admin",
        bootstrap_admin_password="Admin123!",
        bootstrap_admin_roles=["ADMIN"],
        demo_admin_email="admin@example.com",
        demo_admin_username="admin",
        demo_admin_password="Admin123!",
        demo_admin_roles=["ADMIN"],
    )
    await bootstrap_demo_admin(legacy_settings)

    canonical_settings = Settings(
        bootstrap_admin_email="admin@neft.local",
        bootstrap_admin_username="admin",
        bootstrap_admin_password="Neft123!",
        bootstrap_admin_roles=["ADMIN", "PLATFORM_ADMIN"],
        demo_admin_email="admin@neft.local",
        demo_admin_username="admin",
        demo_admin_password="Neft123!",
        demo_admin_roles=["ADMIN", "PLATFORM_ADMIN"],
    )
    await bootstrap_demo_admin(canonical_settings)

    async with db.get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT email, username, password_hash FROM users ORDER BY email",
        )
        rows = await cur.fetchall()
        await cur.execute(
            "SELECT role_code FROM user_roles ur JOIN users u ON ur.user_id = u.id WHERE lower(u.email)=lower(%s)",
            ("admin@neft.local",),
        )
        roles = {r["role_code"] for r in await cur.fetchall()}

    assert len(rows) == 1
    assert rows[0]["email"] == "admin@neft.local"
    assert rows[0]["username"] == "admin"
    assert verify_password("Neft123!", rows[0]["password_hash"])
    assert {"ADMIN", "PLATFORM_ADMIN"}.issubset(roles)

from __future__ import annotations

import pytest
import psycopg

from app import db
from app.bootstrap import bootstrap_demo_admin, seed_demo_client_account
from app.security import verify_password
from app.settings import Settings
from app.tests.migration_helpers import run_auth_migrations


@pytest.mark.anyio
async def test_migrations_and_bootstrap_creates_demo_user():
    try:
        conn = await psycopg.AsyncConnection.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    async with conn.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS user_roles")
        await cur.execute("DROP TABLE IF EXISTS users")
        await conn.commit()
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
            ("admin@example.com",),
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

    async with conn.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS user_roles")
        await cur.execute("DROP TABLE IF EXISTS users")
        await conn.commit()
    await conn.close()

    run_auth_migrations(db.DSN_ASYNC)

    initial_settings = Settings(
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="initial",
        bootstrap_admin_roles=["ADMIN", "SUPERADMIN"],
        demo_admin_email="admin@example.com",
        demo_admin_password="initial",
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
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="changed",
        bootstrap_admin_roles=["ADMIN", "SUPERADMIN"],
        demo_admin_email="admin@example.com",
        demo_admin_password="changed",
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
    assert verify_password("changed", updated_row["password_hash"])
    assert updated_row["password_hash"] != first_hash
    assert sorted(set(roles_after_first)) == sorted(set(roles_after_second)) == ["ADMIN", "SUPERADMIN"]

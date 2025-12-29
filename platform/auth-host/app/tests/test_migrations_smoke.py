from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from app import db
from app.tests.migration_helpers import make_sync_database_url


def _make_alembic_config(database_url: str) -> Config:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "app" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", make_sync_database_url(database_url))
    return cfg


def test_auth_host_migrations_create_tables():
    try:
        conn = psycopg.connect(db.DSN_ASYNC)
    except Exception as exc:  # pragma: no cover - skip when DB unavailable
        pytest.skip(f"Postgres not available: {exc}")

    conn.close()

    alembic_cfg = _make_alembic_config(db.DSN_ASYNC)
    command.upgrade(alembic_cfg, "head")

    with psycopg.connect(db.DSN_ASYNC) as conn_check:
        with conn_check.cursor() as cur:
            cur.execute("SELECT to_regclass('public.users')")
            users_regclass = cur.fetchone()[0]
            cur.execute("SELECT to_regclass('public.user_roles')")
            roles_regclass = cur.fetchone()[0]

    assert users_regclass is not None, "users table missing after alembic upgrade"
    assert roles_regclass is not None, "user_roles table missing after alembic upgrade"

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.diagnostics.db_state import collect_inventory

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_alembic_config(db_url: str) -> Config:
    cfg = Config(str(APP_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(APP_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def postgres_schema(monkeypatch):
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url or not db_url.startswith("postgresql"):
        pytest.skip("PostgreSQL TEST_DATABASE_URL or DATABASE_URL is required for migration smoke tests")

    schema = f"test_schema_{uuid4().hex[:8]}"
    engine = sa.create_engine(db_url, future=True, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DB_SCHEMA", schema)

    yield db_url, schema

    with engine.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_migrations_apply_and_register_version(postgres_schema):
    db_url, schema = postgres_schema

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    inventory = collect_inventory(db_url, schema)

    assert inventory.alembic_versions, "alembic_version should be populated after upgrade"
    assert schema in inventory.schemas

    missing = inventory.missing_tables(REQUIRED_CORE_TABLES)
    assert not missing, f"missing tables after migrations: {missing}"


def test_search_path_applied(postgres_schema):
    db_url, schema = postgres_schema

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    inventory = collect_inventory(db_url, schema)
    assert inventory.search_path is not None
    assert inventory.search_path.lower().startswith(schema.lower())

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DATABASE_URL, DB_SCHEMA


def _make_alembic_config(db_url: str) -> Config:
    app_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(app_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(app_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _create_engine_for_schema(db_url: str):
    if db_url.startswith("postgresql"):
        return create_engine(db_url, connect_args={"options": f"-csearch_path={DB_SCHEMA}"})
    return create_engine(db_url)


def test_core_tables_exist_after_migrations() -> None:
    db_url = os.getenv("DATABASE_URL") or os.getenv("NEFT_DB_URL") or DATABASE_URL

    if not db_url.startswith("postgresql"):
        pytest.skip("schema smoke test requires Postgres database")

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = _create_engine_for_schema(db_url)
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                """
            ),
            {"schema": DB_SCHEMA},
        )
        existing_tables = {row[0] for row in result}

    assert set(REQUIRED_CORE_TABLES).issubset(existing_tables)

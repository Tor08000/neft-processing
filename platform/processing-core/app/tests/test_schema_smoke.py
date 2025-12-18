from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DB_SCHEMA


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
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        pytest.skip("DATABASE_URL is required for schema smoke test")

    if not db_url.startswith("postgresql"):
        pytest.fail("schema smoke test requires PostgreSQL DATABASE_URL")

    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    engine = _create_engine_for_schema(db_url)
    with engine.connect() as conn:
        db_name, current_schema = conn.execute(
            text("SELECT current_database(), current_schema()"),
        ).one()
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
        missing = set(REQUIRED_CORE_TABLES) - existing_tables

        column_types = conn.execute(
            text(
                """
                select table_name, column_name, data_type, udt_name
                from information_schema.columns
                where table_schema = :schema
                  and (table_name, column_name) in (
                    ('operations', 'client_id'),
                    ('operations', 'card_id'),
                    ('operations', 'merchant_id'),
                    ('operations', 'terminal_id'),
                    ('clients', 'id'),
                    ('cards', 'id'),
                    ('merchants', 'id'),
                    ('terminals', 'id')
                  )
                """
            ),
            {"schema": DB_SCHEMA},
        ).mappings()

    types = {
        (row["table_name"], row["column_name"]): (row["data_type"], row["udt_name"])
        for row in column_types
    }

    fk_pairs = [
        (("operations", "client_id"), ("clients", "id")),
        (("operations", "card_id"), ("cards", "id")),
        (("operations", "merchant_id"), ("merchants", "id")),
        (("operations", "terminal_id"), ("terminals", "id")),
    ]

    missing_types = [pair for pair in fk_pairs if pair[0] not in types or pair[1] not in types]
    mismatched_types = {
        (lhs, rhs): (types.get(lhs), types.get(rhs))
        for lhs, rhs in fk_pairs
        if lhs in types and rhs in types and types[lhs] != types[rhs]
    }

    assert not missing, (
        "missing required tables after migrations: "
        f"{sorted(missing)} in database '{db_name}' schema '{DB_SCHEMA}', current schema '{current_schema}'"
    )
    assert not missing_types, f"Missing columns for FK type check: {missing_types}"
    assert not mismatched_types, f"FK column types mismatch: {mismatched_types}"

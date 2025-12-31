from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError
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
        return create_engine(
            db_url,
            connect_args={"options": f"-c search_path={DB_SCHEMA}", "prepare_threshold": 0},
        )
    return create_engine(db_url)


def _resolve_db_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("NEFT_DATABASE_URL")
        or (
            "postgresql+psycopg://neft:neft@postgres:5432/neft"
            if os.getenv("RUNNING_IN_DOCKER") == "1"
            else "postgresql+psycopg://neft:neft@localhost:5432/neft"
        )
    )


def _assert_db_available(db_url: str, *, running_in_docker: bool) -> None:
    try:
        engine = _create_engine_for_schema(db_url)
        with engine.connect():
            return
    except OperationalError as exc:
        if running_in_docker:
            raise
        pytest.skip(f"Postgres is not available for schema smoke test: {exc}")


def test_core_tables_exist_after_migrations() -> None:
    db_url = _resolve_db_url()
    running_in_docker = os.getenv("RUNNING_IN_DOCKER") == "1"

    if not db_url.startswith("postgresql"):
        pytest.fail("schema smoke test requires PostgreSQL DATABASE_URL")

    _assert_db_available(db_url, running_in_docker=running_in_docker)

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

        cards_regclass = conn.execute(
            text("select to_regclass(:regclass)"), {"regclass": f"{DB_SCHEMA}.cards"}
        ).scalar()
        billing_periods_regclass = conn.execute(
            text("select to_regclass(:regclass)"), {"regclass": f"{DB_SCHEMA}.billing_periods"}
        ).scalar()
        created_at_column = conn.execute(
            text(
                """
                select 1
                from information_schema.columns
                where table_schema = :schema
                  and table_name = 'cards'
                  and column_name = 'created_at'
                """
            ),
            {"schema": DB_SCHEMA},
        ).scalar()

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
                    ('terminals', 'id'),
                    ('crm_usage_counters', 'segment_id'),
                    ('crm_subscription_charges', 'segment_id'),
                    ('crm_subscription_period_segments', 'id')
                  )
                """
            ),
            {"schema": DB_SCHEMA},
        ).mappings()
        money_flow_link_node_type_exists = conn.execute(
            text(
                """
                select 1
                from pg_type t
                join pg_namespace n on n.oid = t.typnamespace
                where n.nspname = :schema and t.typname = :enum_name
                """
            ),
            {"schema": DB_SCHEMA, "enum_name": "money_flow_link_node_type"},
        ).scalar()
        subscription_segment_exists = conn.execute(
            text(
                """
                select 1
                from pg_type t
                join pg_namespace n on n.oid = t.typnamespace
                join pg_enum e on e.enumtypid = t.oid
                where n.nspname = :schema
                  and t.typname = :enum_name
                  and e.enumlabel = :enum_value
                """
            ),
            {
                "schema": DB_SCHEMA,
                "enum_name": "money_flow_link_node_type",
                "enum_value": "SUBSCRIPTION_SEGMENT",
            },
        ).scalar()

    types = {
        (row["table_name"], row["column_name"]): (row["data_type"], row["udt_name"])
        for row in column_types
    }

    fk_pairs = [
        (("operations", "client_id"), ("clients", "id")),
        (("operations", "card_id"), ("cards", "id")),
        (("operations", "merchant_id"), ("merchants", "id")),
        (("operations", "terminal_id"), ("terminals", "id")),
        (("crm_usage_counters", "segment_id"), ("crm_subscription_period_segments", "id")),
        (("crm_subscription_charges", "segment_id"), ("crm_subscription_period_segments", "id")),
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
    assert cards_regclass is not None, "cards table is missing after alembic upgrade"
    assert billing_periods_regclass is not None, "billing_periods table is missing after alembic upgrade"
    assert created_at_column is not None, "cards.created_at column is missing after alembic upgrade"
    assert money_flow_link_node_type_exists is not None, "money_flow_link_node_type enum is missing"
    assert subscription_segment_exists is not None, (
        "money_flow_link_node_type enum is missing SUBSCRIPTION_SEGMENT"
    )
    assert not missing_types, f"Missing columns for FK type check: {missing_types}"
    assert not mismatched_types, f"FK column types mismatch: {mismatched_types}"

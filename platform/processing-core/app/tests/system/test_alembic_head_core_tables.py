from __future__ import annotations

import os

import sqlalchemy as sa
from sqlalchemy import create_engine

from app.tests.conftest import _reset_schema, _run_alembic_upgrade


def test_alembic_head_creates_core_tables() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    assert database_url, "DATABASE_URL must be set for alembic head test"

    schema = "system_alembic_head"
    _reset_schema(database_url, schema)
    _run_alembic_upgrade(database_url, schema)

    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        with engine.connect() as conn:
            version_reg = conn.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{schema}.alembic_version_core"},
            ).scalar_one_or_none()
            operations_reg = conn.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{schema}.operations"},
            ).scalar_one_or_none()
            assert version_reg is not None, "alembic_version_core table is missing after upgrade"
            assert operations_reg is not None, "operations table is missing after upgrade"

            enum_names = [
                "operationtype",
                "operationstatus",
                "producttype",
                "riskresult",
            ]
            rows = conn.execute(
                sa.text(
                    """
                    SELECT t.typname
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = :schema AND t.typname = ANY(:names)
                    """
                ),
                {"schema": schema, "names": enum_names},
            ).scalars()
            missing = set(enum_names) - set(rows)
            assert not missing, f"Missing enums after upgrade: {sorted(missing)}"
    finally:
        engine.dispose()


def test_alembic_head_creates_processing_core_operations() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    assert database_url, "DATABASE_URL must be set for alembic head test"

    schema = "processing_core"
    _reset_schema(database_url, schema)
    _run_alembic_upgrade(database_url, schema)

    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={schema}",
            "prepare_threshold": 0,
        },
    )
    try:
        with engine.connect() as conn:
            operations_reg = conn.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{schema}.operations"},
            ).scalar_one_or_none()
            assert operations_reg is not None, "operations table is missing after upgrade"
    finally:
        engine.dispose()

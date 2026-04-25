from __future__ import annotations

import os

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.engine.url import make_url

from app.db import Base
from app.db.schema import DB_SCHEMA
from app.db.types import ExistingEnum
from app.tests.conftest import REQUIRED_TABLES


def _register_enum(
    enum_types: dict[str, dict[str, tuple[str, ...]]],
    *,
    schema: str,
    name: str | None,
    values: tuple[str, ...],
) -> None:
    if not name:
        return
    if not values:
        raise AssertionError(f"Enum {schema}.{name} has no values")
    enum_types.setdefault(schema, {})[name] = values


def _collect_enums(
    metadata: sa.MetaData, default_schema: str, required_tables: set[str]
) -> dict[str, dict[str, tuple[str, ...]]]:
    enum_types: dict[str, dict[str, tuple[str, ...]]] = {}
    for table in metadata.tables.values():
        if table.name not in required_tables:
            continue
        for column in table.columns:
            column_type = column.type
            while isinstance(column_type, sa.ARRAY):
                column_type = column_type.item_type
            if isinstance(column_type, ExistingEnum):
                schema = column_type.schema or default_schema
                _register_enum(
                    enum_types,
                    schema=schema,
                    name=column_type.name,
                    values=tuple(column_type._values),
                )
                continue
            if isinstance(column_type, PGEnum):
                schema = column_type.schema or default_schema
                _register_enum(
                    enum_types,
                    schema=schema,
                    name=column_type.name,
                    values=tuple(column_type.enums),
                )
                continue
            if isinstance(column_type, sa.Enum):
                schema = column_type.schema or default_schema
                _register_enum(
                    enum_types,
                    schema=schema,
                    name=column_type.name,
                    values=tuple(column_type.enums),
                )
                continue
    return enum_types


def _alembic_head_revision() -> str | None:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    if not alembic_ini.exists():
        return None
    cfg = Config(str(alembic_ini))
    return ScriptDirectory.from_config(cfg).get_current_head()


def test_db_schema_consistency() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    try:
        drivername = make_url(database_url).drivername
    except Exception:
        drivername = ""
    if not drivername.startswith("postgresql"):
        pytest.skip("db schema consistency test requires a PostgreSQL DATABASE_URL")
    full_schema_expected = os.getenv("NEFT_FULL_SCHEMA_EXPECTED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    engine = create_engine(
        database_url,
        future=True,
        connect_args={
            "options": f"-c search_path={DB_SCHEMA}",
            "prepare_threshold": 0,
        },
    )
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            required_tables = set(REQUIRED_TABLES)
            if full_schema_expected:
                required_tables = set(Base.metadata.tables)
            expected_tables = {DB_SCHEMA: required_tables}
            for schema, table_names in expected_tables.items():
                actual_tables = set(inspector.get_table_names(schema=schema))
                missing_tables = table_names - actual_tables
                if missing_tables:
                    current_schema, search_path = conn.execute(
                        text("select current_schema(), current_setting('search_path')")
                    ).one()
                    head_revision = _alembic_head_revision()
                    try:
                        current_revision = conn.execute(
                            text(f'SELECT version_num FROM "{schema}".alembic_version_core')
                        ).scalar_one_or_none()
                    except Exception as exc:  # noqa: BLE001 - diagnostics only
                        current_revision = f"error: {exc!r}"
                    raise AssertionError(
                        "Missing required tables after migrations. "
                        f"schema={schema} missing_tables={sorted(missing_tables)} "
                        f"current_schema={current_schema} search_path={search_path} "
                        f"head_revision={head_revision} current_revision={current_revision}"
                    )

            if conn.dialect.name == "postgresql":
                expected_enums = _collect_enums(Base.metadata, DB_SCHEMA, required_tables)
                for schema, enums in expected_enums.items():
                    if not enums:
                        continue
                    rows = conn.execute(
                        text(
                            """
                            SELECT t.typname
                            FROM pg_type t
                            JOIN pg_namespace n ON n.oid = t.typnamespace
                            WHERE n.nspname = :schema AND t.typname = ANY(:names)
                            """
                        ),
                        {"schema": schema, "names": sorted(enums)},
                    ).scalars()
                    existing = set(rows)
                    missing = set(enums) - existing
                    assert not missing, (
                        f"Missing enums in schema {schema}: {sorted(missing)}"
                    )
    finally:
        engine.dispose()

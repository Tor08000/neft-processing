from __future__ import annotations

import os

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from app.db import Base
from app.db.schema import DB_SCHEMA
from app.db.types import ExistingEnum


def _collect_tables(metadata: sa.MetaData, default_schema: str) -> dict[str, set[str]]:
    tables_by_schema: dict[str, set[str]] = {}
    for table in metadata.tables.values():
        schema = table.schema or default_schema
        tables_by_schema.setdefault(schema, set()).add(table.name)
    return tables_by_schema


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


def _collect_enums(metadata: sa.MetaData, default_schema: str) -> dict[str, dict[str, tuple[str, ...]]]:
    enum_types: dict[str, dict[str, tuple[str, ...]]] = {}
    for table in metadata.tables.values():
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


def test_db_schema_consistency() -> None:
    database_url = os.getenv("DATABASE_URL", "")
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
            expected_tables = _collect_tables(Base.metadata, DB_SCHEMA)
            for schema, table_names in expected_tables.items():
                actual_tables = set(inspector.get_table_names(schema=schema))
                missing_tables = table_names - actual_tables
                assert not missing_tables, (
                    f"Missing tables in schema {schema}: {sorted(missing_tables)}"
                )

            if conn.dialect.name == "postgresql":
                expected_enums = _collect_enums(Base.metadata, DB_SCHEMA)
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

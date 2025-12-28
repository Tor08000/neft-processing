from __future__ import annotations

"""Backwards-compatible shim for Alembic helpers."""

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from app.alembic.helpers import (  # noqa: F401,F403
    MIN_VERSION_LENGTH,
    DB_SCHEMA as SCHEMA,
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_unique_expr_index_if_not_exists,
    create_unique_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_mutable_predicate_or_expression_indexes,
    drop_table_if_exists,
    ensure_enum_type_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    enum_exists,
    index_exists,
    is_postgres,
    is_sqlite,
    pg_ensure_enum,
    pg_enum_or_string,
    safe_enum,
    table_exists,
)

inspect = sa_inspect


def create_unique_index_if_not_exists(
    bind,
    index_name: str,
    table_name: str,
    columns_sql: str,
    schema: str,
) -> None:
    """Create a unique expression index if it does not exist."""

    if not is_postgres(bind):
        return

    if "." in index_name:
        index_name = index_name.rsplit(".", 1)[-1]

    query = text(
        """
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema AND c.relname = :index_name AND c.relkind = 'i'
        """
    )
    exists = bind.execute(query, {"schema": schema, "index_name": index_name}).first()
    if exists is not None:
        return

    schema_name = schema or "public"
    bind.exec_driver_sql(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {schema_name}.{table_name} {columns_sql}"
    )


def ensure_alembic_version_length(connection, *, min_length: int = MIN_VERSION_LENGTH) -> None:
    """Ensure ``alembic_version.version_num`` can store long revision ids.

    This reimplementation mirrors ``helpers.ensure_alembic_version_length`` but
    pulls the inspector from the local module namespace so tests can patch
    ``utils.inspect`` without reaching into SQLAlchemy internals.
    """

    dialect_name = getattr(getattr(connection, "dialect", None), "name", None)
    if dialect_name != "postgresql":
        return

    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        connection.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR({min_length}) NOT NULL,
                CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)
            )
            """
        )
        return

    columns = inspector.get_columns("alembic_version")
    version_column = next((col for col in columns if col.get("name") == "version_num"), None)
    if version_column is None:
        connection.exec_driver_sql(
            f"""
            ALTER TABLE alembic_version
            ADD COLUMN version_num VARCHAR({min_length}) NOT NULL
            """
        )
        current_length = None
    else:
        column_type = version_column.get("type")
        current_length = getattr(column_type, "length", None)

    if current_length is None or current_length < min_length:
        connection.exec_driver_sql(
            f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({min_length})"
        )

    pk = inspector.get_pk_constraint("alembic_version")
    pk_columns = set(pk.get("constrained_columns") or [])
    pk_name = pk.get("name")

    if pk_columns != {"version_num"}:
        if pk_name:
            connection.exec_driver_sql(
                f'ALTER TABLE alembic_version DROP CONSTRAINT IF EXISTS "{pk_name}"'
            )

        connection.exec_driver_sql(
            "ALTER TABLE alembic_version"
            " ADD CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)"
        )

__all__ = [
    "MIN_VERSION_LENGTH",
    "column_exists",
    "constraint_exists",
    "create_index_if_not_exists",
    "create_unique_index_if_not_exists",
    "create_table_if_not_exists",
    "drop_index_if_exists",
    "drop_mutable_predicate_or_expression_indexes",
    "drop_table_if_exists",
    "inspect",
    "ensure_alembic_version_length",
    "ensure_enum_type_exists",
    "ensure_pg_enum",
    "ensure_pg_enum_value",
    "enum_exists",
    "index_exists",
    "is_postgres",
    "is_sqlite",
    "pg_ensure_enum",
    "pg_enum_or_string",
    "safe_enum",
    "table_exists",
]

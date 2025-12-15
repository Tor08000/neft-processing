from __future__ import annotations

import logging

from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


logger = logging.getLogger(__name__)


MIN_VERSION_LENGTH = 128


def ensure_alembic_version_length(
    connection: Connection, *, min_length: int = MIN_VERSION_LENGTH
) -> None:
    """Ensure ``alembic_version.version_num`` can store long revision ids.

    The helper is intentionally idempotent and safe to call on every start.
    It only applies to PostgreSQL databases; other dialects are skipped.
    """

    if connection.dialect.name != "postgresql":
        return

    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR({min_length}) NOT NULL,
                    CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)
                )
                """
            )
        )
        return

    columns = inspector.get_columns("alembic_version")
    version_column = next((col for col in columns if col.get("name") == "version_num"), None)
    if version_column is None:
        connection.execute(
            text(
                f"""
                ALTER TABLE alembic_version
                ADD COLUMN version_num VARCHAR({min_length}) NOT NULL
                """
            )
        )
        current_length = None
    else:
        column_type = version_column.get("type")
        current_length = getattr(column_type, "length", None)

    if current_length is None or current_length < min_length:
        connection.execute(
            text(
                f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({min_length})"
            )
        )

    pk = inspector.get_pk_constraint("alembic_version")
    pk_columns = set(pk.get("constrained_columns") or [])
    pk_name = pk.get("name")

    if pk_columns != {"version_num"}:
        if pk_name:
            connection.execute(
                text(
                    f'ALTER TABLE alembic_version DROP CONSTRAINT IF EXISTS "{pk_name}"'
                )
            )

        connection.execute(
            text(
                "ALTER TABLE alembic_version"
                " ADD CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)"
            )
        )


def table_exists(connection: Connection, table_name: str, *, schema: str = "public") -> bool:
    inspector = inspect(connection)
    return table_name in inspector.get_table_names(schema=schema)


def column_exists(
    connection: Connection, table_name: str, column_name: str, *, schema: str = "public"
) -> bool:
    inspector = inspect(connection)
    try:
        columns = inspector.get_columns(table_name, schema=schema)
    except Exception:  # pragma: no cover - defensive
        return False

    return any(column.get("name") == column_name for column in columns)


def index_exists(connection: Connection, index_name: str, *, schema: str = "public") -> bool:
    if connection.dialect.name != "postgresql":
        return False

    result = connection.exec_driver_sql(
        """
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'i'
        """,
        (schema, index_name),
    ).first()
    return result is not None


def create_index_if_not_exists(
    connection: Connection,
    name: str,
    table_name: str,
    columns: list[str] | tuple[str, ...],
    *,
    unique: bool = False,
    schema: str = "public",
    where: str | None = None,
) -> None:
    if connection.dialect.name == "postgresql":
        columns_sql = ", ".join(columns)
        unique_sql = "UNIQUE " if unique else ""
        where_sql = f" WHERE {where}" if where else ""
        logger.info("Ensuring index %s exists on %s", name, table_name)
        connection.exec_driver_sql(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {name} ON {schema}.{table_name} ({columns_sql}){where_sql}"
        )
        return

    if not index_exists(connection, name, schema=schema):
        logger.info("Creating index %s via Alembic API", name)
        op.create_index(name, table_name, columns, unique=unique, schema=schema)


def drop_index_if_exists(
    connection: Connection, name: str, *, schema: str = "public", table_name: str | None = None
) -> None:
    if connection.dialect.name == "postgresql":
        logger.info("Dropping index %s if exists", name)
        connection.exec_driver_sql(f"DROP INDEX IF EXISTS {schema}.{name}")
        return

    if index_exists(connection, name, schema=schema):
        logger.info("Dropping index %s via Alembic API", name)
        op.drop_index(name, table_name=table_name)


def ensure_enum_type_exists(
    connection: Connection,
    *,
    type_name: str,
    values: list[str],
    schema: str = "public",
) -> None:
    if connection.dialect.name != "postgresql":
        return

    exists = connection.exec_driver_sql(
        """
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = %s AND t.typname = %s
        """,
        (schema, type_name),
    ).first()

    if exists:
        logger.info("Skipping creation of enum %s.%s: already exists", schema, type_name)
        return

    values_sql = ", ".join(f"'{value}'" for value in values)
    logger.info("Creating enum %s.%s", schema, type_name)
    connection.exec_driver_sql(
        f"CREATE TYPE {schema}.{type_name} AS ENUM ({values_sql})"
    )

from __future__ import annotations

import logging

from sqlalchemy import inspect
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


def table_exists(connection: Connection, table_name: str, *, schema: str = "public") -> bool:
    if connection.dialect.name == "sqlite":
        result = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).first()
        return result is not None

    result = connection.exec_driver_sql(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
        (schema, table_name),
    ).first()
    return result is not None


def column_exists(
    connection: Connection, table_name: str, column_name: str, *, schema: str = "public"
) -> bool:
    if connection.dialect.name == "sqlite":
        rows = connection.exec_driver_sql(f"PRAGMA table_info('{table_name}')").all()
        return any(row[1] == column_name for row in rows)

    result = connection.exec_driver_sql(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (schema, table_name, column_name),
    ).first()
    return result is not None


def index_exists(connection: Connection, index_name: str, *, schema: str = "public") -> bool:
    if connection.dialect.name == "sqlite":
        result = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        ).first()
        return result is not None

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


def drop_index_if_exists(
    connection: Connection, name: str, *, table_name: str | None = None, schema: str = "public"
) -> None:
    del table_name  # unused Alembic compatibility

    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(f"DROP INDEX IF EXISTS {name}")
        return

    connection.exec_driver_sql(f"DROP INDEX IF EXISTS {schema}.{name}")


def create_index_if_not_exists(
    connection: Connection,
    index_name: str,
    table_name: str,
    columns: list[str] | tuple[str, ...],
    *,
    schema: str = "public",
    unique: bool = False,
    postgresql_where: str | None = None,
    postgresql_using: str | None = None,
    **kwargs,
) -> None:
    del kwargs  # unused kwargs for Alembic compatibility

    if index_exists(connection, index_name, schema=schema):
        logger.info("Skipping creation of index %s: already exists", index_name)
        return

    columns_sql = ", ".join(columns)

    if connection.dialect.name == "postgresql":
        unique_sql = "UNIQUE " if unique else ""
        using_sql = f" USING {postgresql_using}" if postgresql_using else ""
        where_sql = f" WHERE {postgresql_where}" if postgresql_where else ""
        connection.exec_driver_sql(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {schema}.{table_name}{using_sql} ({columns_sql}){where_sql}"
        )
        return

    unique_sql = "UNIQUE " if unique else ""
    connection.exec_driver_sql(
        f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
    )


def enum_type_exists(connection: Connection, type_name: str, *, schema: str = "public") -> bool:
    if connection.dialect.name != "postgresql":
        return False

    result = connection.exec_driver_sql(
        """
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = %s AND t.typname = %s
        """,
        (schema, type_name),
    ).first()
    return result is not None


def ensure_enum_type_exists(
    connection: Connection,
    *,
    type_name: str,
    values: list[str],
    schema: str = "public",
) -> None:
    pg_ensure_enum(connection, type_name, values, schema=schema)


def pg_enum_exists(connection: Connection, name: str, *, schema: str = "public") -> bool:
    """Check if a PostgreSQL enum exists.

    Always returns ``False`` for non-PostgreSQL dialects to make helpers
    idempotent in SQLite test runs.
    """

    if connection.dialect.name != "postgresql":
        return False

    return enum_type_exists(connection, name, schema=schema)


def pg_ensure_enum(
    connection: Connection, name: str, values: list[str], *, schema: str = "public"
) -> None:
    """Create a PostgreSQL enum if it does not already exist.

    Uses a ``DO $$ ... $$`` block for compatibility with PostgreSQL versions that
    lack ``CREATE TYPE ... IF NOT EXISTS``.
    """

    if connection.dialect.name != "postgresql":
        return

    if pg_enum_exists(connection, name, schema=schema):
        logger.info("Skipping creation of enum %s.%s: already exists", schema, name)
        return

    values_sql = ", ".join(f"'{value}'" for value in values)
    logger.info("Creating enum %s.%s", schema, name)
    connection.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = '{schema}' AND t.typname = '{name}'
            ) THEN
                CREATE TYPE {schema}.{name} AS ENUM ({values_sql});
            END IF;
        END $$;
        """
    )

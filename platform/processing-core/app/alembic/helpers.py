from __future__ import annotations

import logging
from typing import Iterable, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

MIN_VERSION_LENGTH = 128


# Dialect helpers

def is_postgres(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


def is_sqlite(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "sqlite"


# Existence checks

def table_exists(bind: Connection, table_name: str, schema: str = "public") -> bool:
    if is_sqlite(bind):
        result = bind.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).first()
        return result is not None

    result = bind.exec_driver_sql(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table_name),
    ).first()
    return result is not None


def column_exists(
    bind: Connection, table_name: str, column_name: str, schema: str = "public"
) -> bool:
    if is_sqlite(bind):
        rows = bind.exec_driver_sql(f"PRAGMA table_info('{table_name}')").all()
        return any(row[1] == column_name for row in rows)

    result = bind.exec_driver_sql(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (schema, table_name, column_name),
    ).first()
    return result is not None


def index_exists(bind: Connection, index_name: str, schema: str = "public") -> bool:
    if is_sqlite(bind):
        result = bind.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
        ).first()
        return result is not None

    query = """
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'i'
    """
    try:
        result = bind.exec_driver_sql(query, (schema, index_name))
    except TypeError:
        formatted = query.replace("%s", "{}").format(schema, index_name)
        result = bind.exec_driver_sql(formatted)

    first = getattr(result, "first", None)
    return callable(first) and first() is not None


def constraint_exists(
    bind: Connection, table_name: str, constraint_name: str, schema: str = "public"
) -> bool:
    if is_sqlite(bind):
        result = bind.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE name=?", (constraint_name,)
        ).first()
        return result is not None

    result = bind.exec_driver_sql(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = %s AND table_name = %s AND constraint_name = %s
        """,
        (schema, table_name, constraint_name),
    ).first()
    return result is not None


def enum_exists(bind: Connection, enum_name: str, schema: str = "public") -> bool:
    if not is_postgres(bind):
        return False

    result = bind.exec_driver_sql(
        """
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = %s AND t.typname = %s
        """,
        (schema, enum_name),
    ).first()
    return result is not None


# Enum helpers

def ensure_pg_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = "public") -> None:
    if not is_postgres(bind):
        return

    values_sql = ", ".join(f"'{value}'" for value in values)
    type_name = enum_name if schema in {None, "", "public"} else f"{schema}.{enum_name}"
    bind.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            BEGIN
                CREATE TYPE {type_name} AS ENUM ({values_sql});
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
        END $$;
        """
    )


def pg_ensure_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = "public") -> None:
    """Alias for ensure_pg_enum for backward compatibility."""

    ensure_pg_enum(bind, enum_name, values=values, schema=schema)


def ensure_enum_type_exists(bind: Connection, type_name: str, values: Sequence[str], schema: str = "public") -> None:
    """Maintain compatibility with older migrations expecting ensure_enum_type_exists."""

    ensure_pg_enum(bind, type_name, values=values, schema=schema)


def safe_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = "public"):
    if is_postgres(bind):
        return postgresql.ENUM(*values, name=enum_name, schema=schema, create_type=False)
    return sa.Enum(*values, name=enum_name, native_enum=False)


# Safe creation helpers

def create_table_if_not_exists(
    bind: Connection, table_name: str, *columns, schema: str = "public", **kwargs
) -> None:
    if table_exists(bind, table_name, schema=schema):
        logger.info("Table %s.%s already exists, skipping", schema, table_name)
        return

    op.create_table(table_name, *columns, schema=schema, **kwargs)


def drop_table_if_exists(bind: Connection, table_name: str, schema: str = "public") -> None:
    if not table_exists(bind, table_name, schema=schema):
        return

    op.drop_table(table_name, schema=schema)


def create_index_if_not_exists(
    bind: Connection,
    index_name: str,
    table_name: str,
    columns: Sequence[str] | Iterable[str],
    *,
    schema: str = "public",
    **kwargs,
) -> None:
    if index_exists(bind, index_name, schema=schema):
        logger.info("Index %s.%s already exists, skipping", schema, index_name)
        return

    operations = getattr(bind, "op_override", op)
    create_fn = getattr(operations, "create_index", None)
    if create_fn is None:
        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table_name} ({', '.join(columns)})"
        bind.exec_driver_sql(sql)
        return

    try:
        create_fn(index_name, table_name, list(columns), schema=schema, **kwargs)
    except TypeError:
        create_fn(index_name, table_name, list(columns), **kwargs)
    except NameError as exc:
        if "proxy" not in str(exc):
            raise
        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {schema}.{table_name} ({', '.join(columns)})"
        bind.exec_driver_sql(sql)


def drop_index_if_exists(bind: Connection, index_name: str, schema: str = "public") -> None:
    if not index_exists(bind, index_name, schema=schema):
        return

    op.drop_index(index_name, schema=schema)


def drop_mutable_predicate_or_expression_indexes(
    bind: Connection, table_name: str, schema: str = "public"
) -> list[str]:
    if not is_postgres(bind):
        return []

    result = bind.exec_driver_sql(
        """
        SELECT idx.relname AS index_name
        FROM pg_index i
        JOIN pg_class tbl ON tbl.oid = i.indrelid
        JOIN pg_class idx ON idx.oid = i.indexrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        WHERE ns.nspname = %s
          AND tbl.relname = %s
          AND (i.indpred IS NOT NULL OR i.indexprs IS NOT NULL)
        """,
        (schema, table_name),
    )

    dropped: list[str] = []
    for (index_name,) in result.fetchall():
        bind.exec_driver_sql(f"DROP INDEX IF EXISTS {schema}.{index_name}")
        dropped.append(index_name)

    return dropped


# Alembic version helper

def ensure_alembic_version_length(
    connection: Connection, *, min_length: int = MIN_VERSION_LENGTH
) -> None:
    """Ensure ``alembic_version.version_num`` can store long revision ids."""

    if connection.dialect.name != "postgresql":
        return

    inspector = sa.inspect(connection)
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

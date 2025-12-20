from __future__ import annotations

import logging
from typing import Iterable, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from app.db.schema import resolve_db_schema

logger = logging.getLogger(__name__)

MIN_VERSION_LENGTH = 128

SCHEMA_RESOLUTION = resolve_db_schema()
DB_SCHEMA = SCHEMA_RESOLUTION.schema


# Dialect helpers

def is_postgres(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


def is_sqlite(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "sqlite"


# Existence checks

def table_exists(bind: Connection, table_name: str, schema: str = DB_SCHEMA) -> bool:
    if is_sqlite(bind):
        result = bind.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).first()
        return result is not None

    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table_name
            """
        ),
        {"schema": schema, "table_name": table_name},
    ).first()
    return result is not None


def column_exists(
    bind: Connection, table_name: str, column_name: str, schema: str = DB_SCHEMA
) -> bool:
    if is_sqlite(bind):
        rows = bind.exec_driver_sql(f"PRAGMA table_info('{table_name}')").all()
        return any(row[1] == column_name for row in rows)

    result = bind.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    ).first()
    return result is not None


def index_exists(bind: Connection, index_name: str, schema: str = DB_SCHEMA) -> bool:
    if is_sqlite(bind):
        result = bind.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:name"),
            {"name": index_name},
        ).first()
        return result is not None

    query = sa.text(
        """
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema AND c.relname = :index_name AND c.relkind = 'i'
        """
    )
    result = bind.execute(query, {"schema": schema, "index_name": index_name})

    first = getattr(result, "first", None)
    return callable(first) and first() is not None


def constraint_exists(
    bind: Connection, table_name: str, constraint_name: str, schema: str = DB_SCHEMA
) -> bool:
    if is_sqlite(bind):
        result = bind.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE name=:name"),
            {"name": constraint_name},
        ).first()
        return result is not None

    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = :schema AND table_name = :table_name AND constraint_name = :constraint_name
            """
        ),
        {"schema": schema, "table_name": table_name, "constraint_name": constraint_name},
    ).first()
    return result is not None


def enum_exists(bind: Connection, enum_name: str, schema: str = DB_SCHEMA) -> bool:
    if not is_postgres(bind):
        return False

    result = bind.execute(
        sa.text(
            """
            SELECT 1 FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = :schema AND t.typname = :enum_name
            """
        ),
        {"schema": schema, "enum_name": enum_name},
    ).first()
    return result is not None


def regclass(conn: Connection, qualified_name: str) -> str | None:
    """Return ``to_regclass`` for a fully qualified object name."""

    return conn.execute(
        sa.text("select to_regclass(:name)"),
        {"name": qualified_name},
    ).scalar_one_or_none()


# Enum helpers

def ensure_pg_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = DB_SCHEMA) -> None:
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


def pg_ensure_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = DB_SCHEMA) -> None:
    """Alias for ensure_pg_enum for backward compatibility."""

    ensure_pg_enum(bind, enum_name, values=values, schema=schema)


def ensure_enum_type_exists(bind: Connection, type_name: str, values: Sequence[str], schema: str = DB_SCHEMA) -> None:
    """Maintain compatibility with older migrations expecting ensure_enum_type_exists."""

    ensure_pg_enum(bind, type_name, values=values, schema=schema)


def ensure_pg_enum_value(bind: Connection, enum_name: str, value: str, schema: str | None = DB_SCHEMA) -> None:
    """Add a value to a PostgreSQL enum type if it's missing (idempotent).
    Safe for repeated runs; no-op on non-PostgreSQL.
    """
    if not is_postgres(bind):
        return

    schema = schema or "public"

    stmt = (
        sa.text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = :enum::text
                  AND e.enumlabel = :value::text
                  AND n.nspname = :schema::text
              )
              THEN
                EXECUTE format(
                  'ALTER TYPE %I.%I ADD VALUE %L',
                  :schema::text, :enum::text, :value::text
                );
              END IF;
            END $$;
            """
        )
        .bindparams(
            sa.bindparam("enum", type_=sa.String()),
            sa.bindparam("value", type_=sa.String()),
            sa.bindparam("schema", type_=sa.String()),
        )
    )

    bind.execute(stmt, {"enum": enum_name, "value": value, "schema": schema})


def safe_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = DB_SCHEMA):
    if is_postgres(bind):
        return postgresql.ENUM(*values, name=enum_name, schema=schema, create_type=False)
    return sa.Enum(*values, name=enum_name, native_enum=False)


def pg_enum_or_string(
    bind: Connection, enum_name: str, values: Sequence[str], *, schema: str = DB_SCHEMA, min_length: int = 32
):
    """Use a PostgreSQL enum when available, otherwise fall back to VARCHAR."""

    length = max(min_length, *(len(value) for value in values))
    if is_postgres(bind):
        return safe_enum(bind, enum_name, values, schema=schema)
    return sa.String(length=length)


def drop_pg_enum_if_exists(bind: Connection, enum_name: str, schema: str = DB_SCHEMA) -> None:
    """Drop PostgreSQL enum type if it exists, skipping other dialects."""

    if not is_postgres(bind):
        return

    schema_name = schema or "public"
    qualified_enum = f"{schema_name}.{enum_name}"
    bind.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = :schema_name
                  AND t.typname = :enum_name
            ) THEN
                EXECUTE format('DROP TYPE IF EXISTS %s', :qualified_enum);
            END IF;
        END $$;
        """,
        {"schema_name": schema_name, "enum_name": enum_name, "qualified_enum": qualified_enum},
    )


# Safe creation helpers

def create_table_if_not_exists(
    bind: Connection, table_name: str, *columns, schema: str = DB_SCHEMA, **kwargs
) -> None:
    if table_exists(bind, table_name, schema=schema):
        logger.info("Table %s.%s already exists, skipping", schema, table_name)
        return

    op.create_table(table_name, *columns, schema=schema, **kwargs)


def drop_table_if_exists(bind: Connection, table_name: str, schema: str = DB_SCHEMA) -> None:
    if not table_exists(bind, table_name, schema=schema):
        return

    op.drop_table(table_name, schema=schema)


def create_index_if_not_exists(
    bind: Connection,
    index_name: str,
    table_name: str,
    columns: Sequence[str] | Iterable[str],
    *,
    schema: str = DB_SCHEMA,
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


def drop_index_if_exists(bind: Connection, index_name: str, schema: str = DB_SCHEMA) -> None:
    if not index_exists(bind, index_name, schema=schema):
        return

    op.drop_index(index_name, schema=schema)


def drop_mutable_predicate_or_expression_indexes(
    bind: Connection, table_name: str, schema: str = DB_SCHEMA
) -> list[str]:
    if not is_postgres(bind):
        return []

    result = bind.execute(
        sa.text(
            """
            SELECT idx.relname AS index_name
            FROM pg_index i
            JOIN pg_class tbl ON tbl.oid = i.indrelid
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
            WHERE ns.nspname = :schema
              AND tbl.relname = :table_name
              AND (i.indpred IS NOT NULL OR i.indexprs IS NOT NULL)
            """
        ),
        {"schema": schema, "table_name": table_name},
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

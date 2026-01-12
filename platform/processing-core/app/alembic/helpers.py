from __future__ import annotations

import logging
from typing import Iterable, Sequence

import sqlalchemy as sa
from sqlalchemy import text
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from app.db.schema import resolve_db_schema

logger = logging.getLogger(__name__)

MIN_VERSION_LENGTH = 128

SCHEMA_RESOLUTION = resolve_db_schema()
DB_SCHEMA = SCHEMA_RESOLUTION.schema
ALEMBIC_VERSION_TABLE = "alembic_version_core"


# Dialect helpers

def is_postgres(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "postgresql"


def is_sqlite(bind: Connection) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", None) == "sqlite"


# Existence checks

def _require_bind(bind: Connection, *, caller: str) -> None:
    if not isinstance(bind, Connection):
        bind_type = type(bind).__name__
        raise TypeError(f"{caller} expected a SQLAlchemy Connection for bind; got {bind_type}.")


def table_exists(bind: Connection, table_name: str, schema: str = DB_SCHEMA) -> bool:
    _require_bind(bind, caller="table_exists")

    if is_sqlite(bind):
        result = bind.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).first()
        return result is not None

    if is_postgres(bind):
        result = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                  AND c.relname = :table_name
                  AND c.relkind IN ('r', 'p')
                """
            ),
            {"schema": schema, "table_name": table_name},
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


def table_exists_real(bind: Connection, schema: str, table_name: str) -> bool:
    _require_bind(bind, caller="table_exists_real")

    if is_postgres(bind):
        result = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                  AND c.relname = :table_name
                  AND c.relkind IN ('r', 'p')
                """
            ),
            {"schema": schema, "table_name": table_name},
        ).first()
        return result is not None

    return table_exists(bind, table_name, schema=schema)


def composite_type_exists(bind: Connection, schema: str, type_name: str) -> bool:
    _require_bind(bind, caller="composite_type_exists")

    if not is_postgres(bind):
        return False

    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = :schema
              AND t.typname = :type_name
              AND t.typtype = 'c'
            """
        ),
        {"schema": schema, "type_name": type_name},
    ).first()
    return result is not None


def drop_composite_type(bind: Connection, schema: str, type_name: str) -> None:
    _require_bind(bind, caller="drop_composite_type")

    if not is_postgres(bind):
        return

    schema_sql = (schema or DB_SCHEMA).replace('"', '""')
    type_sql = type_name.replace('"', '""')
    bind.exec_driver_sql(f'DROP TYPE IF EXISTS "{schema_sql}"."{type_sql}" CASCADE')


def drop_orphan_composite_type_if_needed(
    bind: Connection, type_name: str, schema: str = DB_SCHEMA
) -> None:
    _require_bind(bind, caller="drop_orphan_composite_type_if_needed")

    if table_exists_real(bind, schema, type_name):
        return

    if composite_type_exists(bind, schema, type_name):
        logger.warning(
            "Dropping orphan composite type %s.%s before creating table",
            schema,
            type_name,
        )
        drop_composite_type(bind, schema, type_name)


def drop_orphan_table_type_if_exists(bind: Connection, schema: str, table_name: str) -> None:
    _require_bind(bind, caller="drop_orphan_table_type_if_exists")

    if composite_type_exists(bind, schema, table_name):
        logger.warning(
            "Dropping orphan composite type %s.%s before creating table",
            schema,
            table_name,
        )
        drop_composite_type(bind, schema, table_name)


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

    schema_name = schema or DB_SCHEMA
    if not values:
        raise RuntimeError(f"Enum {schema}.{enum_name} values list is empty")
    values_sql = ", ".join("'{}'".format(value.replace("'", "''")) for value in values)
    schema_sql = schema_name.replace('"', '""')
    enum_sql = enum_name.replace('"', '""')
    bind.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = '{schema_sql}' AND t.typname = '{enum_sql}'
            ) THEN
                CREATE TYPE "{schema_sql}"."{enum_sql}" AS ENUM ({values_sql});
            END IF;
        END $$;
        """
    )


def pg_ensure_enum(bind: Connection, enum_name: str, values: Sequence[str], schema: str = DB_SCHEMA) -> None:
    """Alias for ensure_pg_enum for backward compatibility."""

    ensure_pg_enum(bind, enum_name, values=values, schema=schema)


def ensure_enum_type_exists(bind: Connection, type_name: str, values: Sequence[str], schema: str = DB_SCHEMA) -> None:
    """Maintain compatibility with older migrations expecting ensure_enum_type_exists."""

    ensure_pg_enum(bind, type_name, values=values, schema=schema)


def ensure_pg_enum_value(conn, enum_name: str, value: str, schema: str = DB_SCHEMA) -> None:
    """
    Ensure Postgres enum type contains a given label.
    - conn: SQLAlchemy Connection
    - enum_name: enum type name (without schema)
    - value: enum label to ensure exists
    - schema: schema where enum type lives
    """
    if not is_postgres(conn):
        return

    schema_name = schema or DB_SCHEMA
    value_literal = "'" + value.replace("'", "''") + "'"

    type_exists = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = :schema AND t.typname = :enum_name
            """
        ),
        {"schema": schema_name, "enum_name": enum_name},
    ).scalar()

    if not type_exists:
        create_sql = text(
            f'CREATE TYPE "{schema_name}"."{enum_name}" AS ENUM ({value_literal})'
        )
        try:
            conn.execute(create_sql)
        except sa.exc.DBAPIError as exc:
            if getattr(getattr(exc, "orig", None), "pgcode", None) != "42710":
                raise
        return

    add_sql = text(
        f'ALTER TYPE "{schema_name}"."{enum_name}" ADD VALUE IF NOT EXISTS {value_literal}'
    )
    conn.execute(add_sql)


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

    schema_name = schema or DB_SCHEMA
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
                EXECUTE format('DROP TYPE IF EXISTS %%s', :qualified_enum);
            END IF;
        END $$;
        """,
        {"schema_name": schema_name, "enum_name": enum_name, "qualified_enum": qualified_enum},
    )


# Safe creation helpers

def create_table_if_not_exists(
    bind: Connection,
    table_name: str,
    *table_columns: sa.Column,
    schema: str = DB_SCHEMA,
    columns: Sequence[sa.Column] | None = None,
    indexes: Sequence[tuple[str, Sequence[str]]] | None = None,
    create_fn=None,
    **kwargs,
) -> None:
    _require_bind(bind, caller="create_table_if_not_exists")
    keyword_columns = columns

    if table_columns and keyword_columns is not None:
        raise TypeError("Columns must be provided either positionally or via the `columns` keyword, not both.")

    column_list = list(table_columns or keyword_columns or [])
    index_definitions = list(indexes or [])
    table_present = table_exists_real(bind, schema, table_name)
    if table_present:
        logger.info("Table %s.%s already exists, skipping creation", schema, table_name)
        return

    if composite_type_exists(bind, schema, table_name):
        schema_name = schema or DB_SCHEMA
        print(f"[alembic] dropping orphan composite type {schema_name}.{table_name}")
        logger.warning(
            "Dropping orphan composite type %s.%s before creating table",
            schema_name,
            table_name,
        )
        drop_composite_type(bind, schema_name, table_name)

    operations = getattr(bind, "op_override", op)

    if create_fn is not None:
        create_fn()
    elif not column_list:
        raise TypeError("No columns provided for table creation")
    else:
        operations.create_table(table_name, *column_list, schema=schema, **kwargs)

    for index_name, index_columns in index_definitions:
        create_index_if_not_exists(bind, index_name, table_name, index_columns, schema=schema)


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


def create_unique_index_if_not_exists(
    bind: Connection,
    index_name: str,
    table_name: str,
    columns: Sequence[str] | Iterable[str],
    *,
    schema: str = DB_SCHEMA,
) -> None:
    if isinstance(columns, str):
        raise TypeError("columns must be a list/tuple of column names, not a string")

    if index_exists(bind, index_name, schema=schema):
        logger.info("Index %s.%s already exists, skipping", schema, index_name)
        return

    schema_name = schema or DB_SCHEMA
    sql = f"CREATE UNIQUE INDEX {index_name} ON {schema_name}.{table_name} ({', '.join(columns)})"
    bind.exec_driver_sql(sql)


def create_unique_expr_index_if_not_exists(
    bind: Connection,
    index_name: str,
    table_name: str,
    expr_sql: str,
    *,
    schema: str = DB_SCHEMA,
) -> None:
    if index_exists(bind, index_name, schema=schema):
        logger.info("Index %s.%s already exists, skipping", schema, index_name)
        return

    schema_name = schema or DB_SCHEMA
    sql = f"CREATE UNIQUE INDEX {index_name} ON {schema_name}.{table_name} {expr_sql}"
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
    """Ensure ``alembic_version_core.version_num`` can store long revision ids."""

    if connection.dialect.name != "postgresql":
        return

    inspector = sa.inspect(connection)
    if ALEMBIC_VERSION_TABLE not in inspector.get_table_names():
        connection.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS {ALEMBIC_VERSION_TABLE} (
                version_num VARCHAR({min_length}) NOT NULL,
                CONSTRAINT {ALEMBIC_VERSION_TABLE}_pkey PRIMARY KEY (version_num)
            )
            """
        )
        return

    columns = inspector.get_columns(ALEMBIC_VERSION_TABLE)
    version_column = next((col for col in columns if col.get("name") == "version_num"), None)
    if version_column is None:
        connection.exec_driver_sql(
            f"""
            ALTER TABLE {ALEMBIC_VERSION_TABLE}
            ADD COLUMN version_num VARCHAR({min_length}) NOT NULL
            """
        )
        current_length = None
    else:
        column_type = version_column.get("type")
        current_length = getattr(column_type, "length", None)

    if current_length is None or current_length < min_length:
        connection.exec_driver_sql(
            f"ALTER TABLE {ALEMBIC_VERSION_TABLE} ALTER COLUMN version_num TYPE VARCHAR({min_length})"
        )

    pk = inspector.get_pk_constraint(ALEMBIC_VERSION_TABLE)
    pk_columns = set(pk.get("constrained_columns") or [])
    pk_name = pk.get("name")

    if pk_columns != {"version_num"}:
        if pk_name:
            connection.exec_driver_sql(
                f'ALTER TABLE {ALEMBIC_VERSION_TABLE} DROP CONSTRAINT IF EXISTS "{pk_name}"'
            )

        connection.exec_driver_sql(
            f"ALTER TABLE {ALEMBIC_VERSION_TABLE}"
            f" ADD CONSTRAINT {ALEMBIC_VERSION_TABLE}_pkey PRIMARY KEY (version_num)"
        )

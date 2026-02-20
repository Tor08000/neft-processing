from __future__ import annotations

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, text
from sqlalchemy.pool import NullPool

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from db.schema import quote_schema

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

config.set_main_option("sqlalchemy.url", DATABASE_URL)
schema = "processing_core"
version_table = "alembic_version_core"
target_metadata = None
config.set_main_option("version_table", version_table)
config.set_main_option("version_table_schema", schema)


_PARALLEL_TABLE_EXPLICITLY_ALLOWED = {
    (schema, version_table),
    ("processing_auth", "alembic_version_auth"),
}
_PARALLEL_TABLE_ALLOWED_SCHEMA_PREFIXES = ("processing_",)


def _find_parallel_version_tables(connection) -> list[tuple[str, str]]:
    rows = connection.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_name LIKE 'alembic_version%'
            ORDER BY table_schema, table_name
            """
        )
    ).all()
    return [(str(table_schema), str(table_name)) for table_schema, table_name in rows]


def _is_allowlisted_other_service_table(table_schema: str, table_name: str) -> bool:
    if (table_schema, table_name) in _PARALLEL_TABLE_EXPLICITLY_ALLOWED:
        return True
    return table_schema.startswith(_PARALLEL_TABLE_ALLOWED_SCHEMA_PREFIXES)


def _forbid_parallel_version_tables(connection) -> None:
    violations: list[tuple[str, str]] = []
    for table_schema, table_name in _find_parallel_version_tables(connection):
        if table_schema == "public":
            violations.append((table_schema, table_name))
            continue
        if table_schema == schema and table_name != version_table:
            violations.append((table_schema, table_name))
            continue
        if _is_allowlisted_other_service_table(table_schema, table_name):
            continue

    if not violations:
        return

    table_names = ", ".join(f"{table_schema}.{table_name}" for table_schema, table_name in violations)
    raise RuntimeError(
        "Detected forbidden Alembic version tables: "
        f"{table_names}. Forbidden: any public.alembic_version% table and any "
        f"{schema}.alembic_version% table except {schema}.{version_table}."
    )


def _assert_non_empty_core_version_table_after_upgrade(connection, command_name: str) -> None:
    if command_name != "upgrade":
        return

    row_count = connection.execute(
        text("SELECT COUNT(*) FROM processing_core.alembic_version_core")
    ).scalar_one()
    if row_count > 0:
        return

    rows = connection.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = 'version_num'
              AND table_name ILIKE 'alembic_version%'
            ORDER BY table_schema, table_name
            """
        )
    ).all()
    tables = ", ".join(f"{table_schema}.{table_name}" for table_schema, table_name in rows) or "<none>"
    raise RuntimeError(
        "processing_core.alembic_version_core is empty after upgrade; detected version_num tables: "
        f"{tables}."
    )


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version_core",
        version_table_schema="processing_core",
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _configure(connection, command_name: str | None) -> None:
    quoted_schema = quote_schema(schema)
    connection.execute(text(f"SET search_path TO {quoted_schema}, public"))
    transaction_per_migration = command_name in {"upgrade", "downgrade"}
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version_core",
        version_table_schema="processing_core",
        transaction_per_migration=transaction_per_migration,
    )


def _ensure_core_schema(connection) -> None:
    quoted_schema = quote_schema(schema)
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))


def _log_version_table_diagnostics(connection) -> None:
    current_schema = connection.execute(text("SELECT current_schema()")).scalar_one()
    search_path = connection.execute(text("SHOW search_path")).scalar_one()
    config.print_stdout(
        "Alembic version table config: %s.%s; current_schema=%s; search_path=%s",
        schema,
        version_table,
        current_schema,
        search_path,
    )


def _detect_alembic_cmd() -> str:
    known_commands = {
        "upgrade",
        "downgrade",
        "stamp",
        "current",
        "history",
        "heads",
        "revision",
    }
    for arg in sys.argv[1:]:
        if arg in known_commands:
            return arg
    return "unknown"


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
        future=True,
        connect_args={
            "options": f"-c search_path={schema},public",
            "prepare_threshold": 0,
        },
    )

    with connectable.connect() as connection:
        command_name = _detect_alembic_cmd()
        command_name = str(command_name).lower()
        skip_preflight = command_name in {"current", "history", "heads"}
        _ensure_core_schema(connection)
        if not skip_preflight:
            _forbid_parallel_version_tables(connection)
        _configure(connection, command_name)
        _log_version_table_diagnostics(connection)
        if command_name in {"current", "history", "heads", "branches", "show"}:
            context.run_migrations()
        else:
            with context.begin_transaction():
                context.run_migrations()
            _assert_non_empty_core_version_table_after_upgrade(connection, command_name)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

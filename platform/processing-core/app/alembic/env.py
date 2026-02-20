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
version_column_length = 128
target_metadata = None
config.set_main_option("version_table", version_table)
config.set_main_option("version_table_schema", schema)

configure_kwargs = {
    "target_metadata": target_metadata,
    "include_schemas": True,
    "version_table": version_table,
    "version_table_schema": schema,
}

_PARALLEL_TABLE_ALLOWED = {(schema, version_table)}


def _find_parallel_version_tables(connection) -> list[tuple[str, str]]:
    rows = connection.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_name LIKE 'alembic_version%'
              AND NOT (table_schema = :schema AND table_name = :version_table)
            ORDER BY table_schema, table_name
            """
        ),
        {"schema": schema, "version_table": version_table},
    ).all()
    return [(str(table_schema), str(table_name)) for table_schema, table_name in rows]


def _forbid_parallel_version_tables(connection) -> None:
    parallel_tables = _find_parallel_version_tables(connection)
    if not parallel_tables:
        return

    app_env = os.getenv("APP_ENV", "prod").strip().lower()
    allow_cleanup = os.getenv("ALLOW_DEV_VERSION_TABLE_CLEANUP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    should_auto_cleanup = app_env != "prod" or allow_cleanup

    cleanup_candidates = [
        (table_schema, table_name)
        for table_schema, table_name in parallel_tables
        if table_schema == "public"
        and table_name.startswith("alembic_version")
        and (table_schema, table_name) not in _PARALLEL_TABLE_ALLOWED
    ]

    if should_auto_cleanup and cleanup_candidates:
        for table_schema, table_name in cleanup_candidates:
            connection.execute(text(f'DROP TABLE IF EXISTS "{table_schema}"."{table_name}"'))

        parallel_tables = _find_parallel_version_tables(connection)
        if not parallel_tables:
            return

    table_names = ", ".join(f"{table_schema}.{table_name}" for table_schema, table_name in parallel_tables)
    cleanup_command = (
        "docker compose exec -T postgres psql -U ${POSTGRES_USER:-neft} -d ${POSTGRES_DB:-neft} "
        "-c \"DO $$ DECLARE r RECORD; BEGIN FOR r IN "
        "(SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_type='BASE TABLE' AND table_name LIKE 'alembic_version%') "
        "LOOP EXECUTE format('DROP TABLE IF EXISTS public.%I', r.table_name); END LOOP; END $$;\""
    )
    raise RuntimeError(
        "Detected parallel Alembic version tables that can desync migration state: "
        f"{table_names}. Keep only {schema}.{version_table}; drop/repair extra tables in dev "
        "or migrate their data into processing_core.alembic_version_core before rerunning upgrade. "
        f"Quick fix command: {cleanup_command}"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        **configure_kwargs,
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
        **configure_kwargs,
        transaction_per_migration=transaction_per_migration,
    )


def _ensure_version_table(connection) -> None:
    quoted_schema = quote_schema(schema)
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS "
            f"{quoted_schema}.{version_table} (version_num VARCHAR({version_column_length}) PRIMARY KEY)"
        )
    )
    current_length = connection.execute(
        text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
              AND column_name = 'version_num'
            """
        ),
        {"schema": schema, "table_name": version_table},
    ).scalar()
    if current_length is not None and current_length < version_column_length:
        connection.execute(
            text(
                "ALTER TABLE "
                f"{quoted_schema}.{version_table} "
                f"ALTER COLUMN version_num TYPE VARCHAR({version_column_length})"
            )
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
        if not skip_preflight:
            _ensure_version_table(connection)
            _forbid_parallel_version_tables(connection)
        else:
            quoted_schema = quote_schema(schema)
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
        _configure(connection, command_name)
        if command_name in {"current", "history", "heads", "branches", "show"}:
            context.run_migrations()
        else:
            with context.begin_transaction():
                context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

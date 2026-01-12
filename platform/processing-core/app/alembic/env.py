from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

from app.db.schema import quote_schema, resolve_db_schema

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

config.set_main_option("sqlalchemy.url", DATABASE_URL)
schema_resolution = resolve_db_schema()
schema = schema_resolution.schema
version_table = "alembic_version_core"
version_column_length = 128
config.set_main_option("version_table", version_table)
config.set_main_option("version_table_schema", schema)


def run_migrations_offline() -> None:
    msg = "Offline migrations are not supported; provide DATABASE_URL for online run."
    raise RuntimeError(msg)


def _configure(connection, command_name: str | None) -> None:
    quoted_schema = quote_schema(schema)
    connection.execute(text(f"SET search_path TO {quoted_schema}, public"))
    transaction_per_migration = command_name in {"upgrade", "downgrade"}
    context.configure(
        connection=connection,
        version_table=version_table,
        version_table_schema=schema,
        include_schemas=True,
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


def _get_command_name() -> str | None:
    alembic_context = context.get_context()
    command_opts = getattr(alembic_context, "command_opts", None)
    command_name = getattr(command_opts, "cmd", None)
    if command_name:
        return command_name
    config_opts = getattr(getattr(alembic_context, "config", None), "cmd_opts", None)
    return getattr(config_opts, "cmd", None)


def run_migrations_online() -> None:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        connect_args={
            "options": f"-c search_path={schema},public",
            "prepare_threshold": 0,
        },
    )

    with engine.connect() as connection:
        preflight_connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        _ensure_version_table(preflight_connection)
        command_name = _get_command_name()
        _configure(connection, command_name)
        if command_name in {"current", "history", "heads", "branches", "show"}:
            context.run_migrations()
        else:
            with context.begin_transaction():
                context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

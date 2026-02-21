from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import command, context
from sqlalchemy import engine_from_config, pool

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = None


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
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS processing_core")
        connection.exec_driver_sql("SET search_path TO processing_core, public")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table="alembic_version_core",
            version_table_schema="processing_core",
        )

        migration_context = context.get_context()
        print(
            "[alembic] context.version_table=",
            migration_context.version_table,
            "context.version_table_schema=",
            migration_context.version_table_schema,
        )

        migration_context._ensure_version_table()

        pre_count = connection.exec_driver_sql(
            "select count(*) from processing_core.alembic_version_core"
        ).scalar_one()
        print(f"[alembic] version rows before run_migrations={pre_count}")

        with context.begin_transaction():
            context.run_migrations()

        post_count = connection.exec_driver_sql(
            "select count(*) from processing_core.alembic_version_core"
        ).scalar_one()
        print(f"[alembic] version rows after run_migrations={post_count}")

        if _detect_alembic_cmd().lower() == "upgrade":
            if post_count == 0:
                app_env = os.getenv("APP_ENV", "").lower()
                domain_tables_exist = bool(
                    connection.exec_driver_sql(
                        """
                        select exists (
                            select 1
                            from information_schema.tables
                            where table_schema = 'processing_core'
                              and table_type = 'BASE TABLE'
                              and table_name <> 'alembic_version_core'
                        )
                        """
                    ).scalar_one()
                )

                print(
                    "[alembic] version table empty after run_migrations; "
                    f"app_env={app_env or 'unset'} domain_tables_exist={domain_tables_exist}"
                )

                if app_env == "dev" and domain_tables_exist:
                    print("[alembic] APP_ENV=dev recovery: running alembic stamp head")
                    command.stamp(config, "head")
                    post_stamp_count = connection.exec_driver_sql(
                        "select count(*) from processing_core.alembic_version_core"
                    ).scalar_one()
                    print(f"[alembic] version rows after stamp={post_stamp_count}")
                    if post_stamp_count == 0:
                        raise RuntimeError(
                            "alembic stamp head did not populate processing_core.alembic_version_core"
                        )
                else:
                    raise RuntimeError(
                        "alembic upgrade completed but processing_core.alembic_version_core is empty; "
                        "failing to prevent masked migration state"
                    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

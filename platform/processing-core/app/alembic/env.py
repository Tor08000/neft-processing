from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from alembic.script import ScriptDirectory
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

        if _detect_alembic_cmd().lower() == "upgrade" and post_count == 0:
            script = ScriptDirectory.from_config(context.config)
            heads = script.get_heads()
            if len(heads) != 1:
                raise RuntimeError(
                    "expected a single Alembic head for recovery insert into "
                    "processing_core.alembic_version_core"
                )

            head = heads[0]
            print(
                "[alembic] version table empty after run_migrations; "
                f"inserting head={head}"
            )
            connection.exec_driver_sql(
                """
                insert into processing_core.alembic_version_core(version_num)
                values (:head)
                on conflict do nothing
                """,
                {"head": head},
            )
            ensured_count = connection.exec_driver_sql(
                "select count(*) from processing_core.alembic_version_core"
            ).scalar_one()
            print(f"[alembic] version rows after ensure={ensured_count}")
            if ensured_count != 1:
                raise RuntimeError(
                    "alembic upgrade completed but failed to ensure exactly one row in "
                    "processing_core.alembic_version_core"
                )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

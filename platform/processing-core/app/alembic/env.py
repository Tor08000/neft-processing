from __future__ import annotations

import os
import sys
from logging import getLogger
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import make_url
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
logger = getLogger(__name__)
MIGRATIONS_LOCK_KEY = "processing_core_migrations"
CORE_SCHEMA = "processing_core"


def _url_is_postgresql(url: str) -> bool:
    try:
        return make_url(url).get_backend_name() == "postgresql"
    except Exception:
        return False


def run_migrations_offline() -> None:
    schema_resolved = CORE_SCHEMA if _url_is_postgresql(DATABASE_URL) else None
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version_core",
        version_table_schema=schema_resolved,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        is_postgresql = connection.dialect.name == "postgresql"
        schema_resolved = CORE_SCHEMA if is_postgresql else None

        if is_postgresql:
            connection.exec_driver_sql(
                f"CREATE SCHEMA IF NOT EXISTS {CORE_SCHEMA}"
            )
            connection.exec_driver_sql(
                f"SET search_path TO {CORE_SCHEMA}, public"
            )
            connection.commit()

        locked = False
        try:
            if is_postgresql:
                connection.exec_driver_sql(
                    f"SELECT pg_advisory_lock(hashtext('{MIGRATIONS_LOCK_KEY}'))"
                )
                locked = True

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                version_table="alembic_version_core",
                version_table_schema=schema_resolved,
            )

            with context.begin_transaction():
                context.run_migrations()

            if connection.in_transaction():
                logger.warning(
                    "[alembic] connection still in transaction after supposed COMMIT; forcing commit now"
                )
                connection.commit()

            assert not connection.in_transaction(), (
                "connection transaction remained open after migrations; "
                "check for implicit SQL outside Alembic transaction handling"
            )

            context.config.print_stdout("[alembic] action=COMMIT")
            logger.info("[alembic] action=COMMIT")
        finally:
            if locked:
                connection.exec_driver_sql(
                    f"SELECT pg_advisory_unlock(hashtext('{MIGRATIONS_LOCK_KEY}'))"
                )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

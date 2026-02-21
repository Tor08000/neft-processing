from __future__ import annotations

import os
import sys
from logging import getLogger
from logging.config import fileConfig
from pathlib import Path

from alembic import context
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


def run_migrations_online() -> None:
    validate_only_raw = os.getenv("ALEMBIC_VALIDATE_ONLY", "0")
    validate_only = validate_only_raw == "1"
    validate_only_value = "1" if validate_only else "0"
    context.config.print_stdout("[alembic] validate_only=%s", validate_only_value)
    logger.info("[alembic] validate_only=%s", validate_only_value)

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

        trans = connection.begin()
        try:
            context.run_migrations()

            if validate_only:
                trans.rollback()
                context.config.print_stdout("[alembic] action=ROLLBACK")
                logger.warning("[alembic] action=ROLLBACK")
            else:
                trans.commit()
                context.config.print_stdout("[alembic] action=COMMIT")
                logger.info("[alembic] action=COMMIT")
        except Exception:
            trans.rollback()
            context.config.print_stdout("[alembic] action=ROLLBACK")
            logger.exception("[alembic] action=ROLLBACK due to exception")
            raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# services/core-api/app/alembic/env.py
import logging
import os
import sys
from logging.config import fileConfig
from typing import Any

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine.url import make_url

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db import DB_SCHEMA, Base  # type: ignore  # noqa: E402
from app.alembic.utils import ensure_alembic_version_length  # noqa: E402
from app import models as _models  # noqa: F401  # E402: ensure models are registered

logger = logging.getLogger(__name__)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def resolve_db_url() -> str:
    """Получить URL подключения к БД только из переменной окружения."""

    try:
        db_url = os.environ["DATABASE_URL"]
    except KeyError as exc:  # noqa: PERF203 - explicit error preferred for startup clarity
        raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

    config.set_main_option("sqlalchemy.url", db_url)

    safe_url = make_url(db_url).render_as_string(hide_password=True)
    logger.info("Using database URL for alembic: %s", safe_url)

    return db_url


def log_metadata_state(prefix: str = "") -> None:
    tables = list(Base.metadata.tables.keys())
    sample_tables = tables[:30]
    logger.info("%sSQLAlchemy metadata contains %d tables: %s", prefix, len(tables), sample_tables)


db_url = resolve_db_url()

# Все ORM-модели (Client, User, потом Operation и т.д.)
target_metadata = Base.metadata

log_metadata_state()


def run_migrations_offline() -> None:
    msg = "Offline migrations are not supported; provide DATABASE_URL for online run."
    raise RuntimeError(msg)


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме (с реальным подключением к БД)."""
    connectable = sa.engine_from_config(  # type: ignore[attr-defined]
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError(
                f"Alembic migrations require PostgreSQL engine, got '{connection.dialect.name}'",
            )

        current_db, current_schema, server_ip, server_port = connection.exec_driver_sql(
            "SELECT current_database(), current_schema(), inet_server_addr(), inet_server_port();",
        ).first()
        logger.info(
            "Connected to database=%s schema=%s at %s:%s", current_db, current_schema, server_ip, server_port
        )

        if DB_SCHEMA:
            search_path_sql = f"SET search_path TO {DB_SCHEMA}, public"
            connection.exec_driver_sql(search_path_sql)
            logger.info("Set search_path for migrations to %s", search_path_sql.removeprefix("SET search_path TO "))

        search_path_row = connection.exec_driver_sql("SHOW search_path").scalar_one()
        logger.info("Effective search_path is %s", search_path_row)

        ensure_alembic_version_length(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
            transactional_ddl=True,
            version_table="alembic_version",
            version_table_schema=None,
            as_sql=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

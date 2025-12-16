# services/core-api/app/alembic/env.py
import logging
import os
import sys
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db import Base, DATABASE_URL  # type: ignore  # noqa: E402
from app.alembic.utils import ensure_alembic_version_length
from app import models as _models  # noqa: F401  # E402: ensure models are registered

logger = logging.getLogger(__name__)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def resolve_db_url() -> str:
    """Получить URL подключения к БД из окружения или alembic.ini."""

    env_url = os.getenv("DATABASE_URL") or os.getenv("NEFT_DB_URL")
    ini_url = config.get_main_option("sqlalchemy.url")
    db_url = env_url or ini_url

    if not db_url:
        raise RuntimeError("DATABASE_URL not set and sqlalchemy.url missing")

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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        fingerprint = connection.exec_driver_sql(
            "SELECT current_database(), current_user, inet_server_addr(), inet_server_port();"
        ).first()
        logger.info(
            "Alembic DB fingerprint: database=%s user=%s host=%s port=%s",
            fingerprint[0],
            fingerprint[1],
            fingerprint[2],
            fingerprint[3],
        )

        connection.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS public.alembic_version (
              version_num VARCHAR(128) NOT NULL PRIMARY KEY
            )
            """
        )

        ensure_alembic_version_length(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
            compare_server_default=True,
            version_table="alembic_version",
            version_table_schema="public",
            version_table_column_type=sa.String(length=128),
            transactional_ddl=True,
            as_sql=False,
        )

        if not target_metadata.tables:
            raise RuntimeError(
                "Alembic target_metadata is empty — migrations would not execute any DDL"
            )

        with context.begin_transaction():
            context.run_migrations()

        version_exists = connection.exec_driver_sql(
            "select to_regclass('public.alembic_version')"
        ).scalar()
        if version_exists is None:
            raise RuntimeError(
                "alembic_version is missing after migrations — migrations did not apply"
            )

        merchants_exists = connection.exec_driver_sql(
            "select to_regclass('public.merchants')"
        ).scalar()
        if merchants_exists is None:
            raise RuntimeError("public.merchants missing after migrations — schema was not created")


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

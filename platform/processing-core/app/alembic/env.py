# services/core-api/app/alembic/env.py
import logging
import os
import sys
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from alembic.runtime.migration import MigrationContext
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import Base, DATABASE_URL  # type: ignore  # noqa: E402
from app import models  # noqa: F401,E402
from app.models import operation  # noqa: F401,E402
from app.alembic.utils import ensure_alembic_version_length

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


db_url = resolve_db_url()

# Все ORM-модели (Client, User, потом Operation и т.д.)
target_metadata = Base.metadata


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
        try:
            db_info = connection.exec_driver_sql(
                "SELECT current_database(), current_user, inet_server_addr(), inet_server_port()"
            ).first()
        except Exception as exc:  # pragma: no cover - diagnostic only
            logger.warning("Could not fetch connection diagnostics: %s", exc)
        else:
            logger.info(
                "Connected to database=%s user=%s host=%s port=%s",
                db_info[0],
                db_info[1],
                db_info[2],
                db_info[3],
            )

        migration_context = MigrationContext.configure(
            connection,
            opts={
                "version_table": "alembic_version",
                "version_table_schema": "public",
                "version_table_column_type": sa.String(length=128),
                "as_sql": False,
            },
        )

        if not migration_context._has_version_table():
            logger.info("alembic_version table missing; creating via MigrationContext")
            migration_context._ensure_version_table()

        ensure_alembic_version_length(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table="alembic_version",
            version_table_schema="public",
            version_table_column_type=sa.String(length=128),
            as_sql=False,
        )

        with context.begin_transaction():
            context.run_migrations()

        inspector = sa.inspect(connection)
        if "alembic_version" not in inspector.get_table_names(schema="public"):
            raise RuntimeError("alembic_version table was not created during migrations")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

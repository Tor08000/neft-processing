# services/core-api/app/alembic/env.py
import logging
import os
import sys
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import Base, DATABASE_URL  # type: ignore  # noqa: E402
from app import models  # noqa: F401,E402
from app.models import operation  # noqa: F401,E402
from app.alembic.utils import MIN_VERSION_LENGTH, ensure_alembic_version_length

logger = logging.getLogger(__name__)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def resolve_db_url() -> str:
    """Получить URL подключения к БД из окружения или alembic.ini."""

    env_url = os.getenv("DATABASE_URL")
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
        # ВАЖНО: не делать connection.begin() — Alembic сам управляет транзакцией
        connection.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR({MIN_VERSION_LENGTH}) NOT NULL,
                CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)
            )
            """
        )
        ensure_alembic_version_length(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table_column_type=sa.String(length=128),
            as_sql=False,
        )

        with context.begin_transaction():
            context.run_migrations()

        inspector = sa.inspect(connection)
        if "alembic_version" not in inspector.get_table_names():
            raise RuntimeError("alembic_version table was not created during migrations")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

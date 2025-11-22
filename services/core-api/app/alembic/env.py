# services/core-api/app/alembic/env.py
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from db.base import Base
from db import models  # noqa: F401  # ВАЖНО: чтобы Alembic увидел Client, User и будущие модели

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Берём DSN из ENV, иначе — дефолт, совпадающий с core-api
db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://neft:neftpass@postgres:5432/neft",
)
config.set_main_option("sqlalchemy.url", db_url)

# Все ORM-модели (Client, User, потом Operation и т.д.)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в offline-режиме (генерация SQL без подключения к БД)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме (с реальным подключением к БД)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from __future__ import annotations

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

from app.db import Base, make_engine_kwargs  # type: ignore  # noqa: E402
from app.db.schema import resolve_db_schema, schema_resolution_line  # noqa: E402

logger = logging.getLogger(__name__)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _safe_x_arguments() -> dict[str, Any]:
    try:
        return context.get_x_argument(as_dictionary=True)
    except Exception:  # pragma: no cover - defensive for early imports
        return {}


x_arguments = _safe_x_arguments()
DEBUG_SQL = os.getenv("DB_DEBUG_SQL") == "1" or str(x_arguments.get("debug_sql", "")).lower() in {
    "1",
    "true",
    "yes",
}


def resolve_db_url() -> str:
    """Получить URL подключения к БД только из переменной окружения."""

    try:
        db_url = os.environ["DATABASE_URL"]
    except KeyError as exc:  # noqa: PERF203 - explicit error preferred for startup clarity
        raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

    config.set_main_option("sqlalchemy.url", db_url)
    config.set_main_option("sqlalchemy.echo", str(DEBUG_SQL).lower())

    safe_url = make_url(db_url).render_as_string(hide_password=True)
    logger.info("Using database URL for alembic: %s", safe_url)

    if DEBUG_SQL:
        logger.info("debug_sql flag enabled: forcing SQLAlchemy echo and detailed transaction logging")

    return db_url


db_url = resolve_db_url()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    msg = "Offline migrations are not supported; provide DATABASE_URL for online run."
    raise RuntimeError(msg)


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме (с реальным подключением к БД)."""

    schema_resolution = resolve_db_schema()
    connectable = sa.create_engine(
        db_url,
        **make_engine_kwargs(
            db_url,
            schema=schema_resolution.target_schema,
            poolclass=pool.NullPool,
            echo=DEBUG_SQL,
        ),
    )

    if DEBUG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    logger.info(
        "Alembic target schema resolved: %s",
        schema_resolution_line(schema_resolution.target_schema, schema_resolution.source),
    )

    with connectable.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError(
                f"Alembic migrations require PostgreSQL engine, got '{connection.dialect.name}'",
            )

        connection.execute(sa.text(schema_resolution.search_path_sql))
        logger.info("Set search_path for migrations to %s", schema_resolution.search_path)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table="alembic_version",
            version_table_schema=schema_resolution.target_schema,
            transactional_ddl=True,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

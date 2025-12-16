# services/core-api/app/alembic/env.py
import importlib
import logging
import os
import pkgutil
import sys
from logging.config import fileConfig
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from alembic.runtime.migration import MigrationContext
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import InvalidRequestError

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db import Base, DATABASE_URL  # type: ignore  # noqa: E402
from app.alembic.utils import ensure_alembic_version_length

logger = logging.getLogger(__name__)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _clear_models_aliases() -> None:
    aliases = [name for name in sys.modules if name == "models" or name.startswith("models.")]
    if aliases:
        logger.warning("Found unexpected models.* aliases in sys.modules: %s", aliases)
        for alias in aliases:
            sys.modules.pop(alias, None)


def import_models_once() -> None:
    """Safely load models so metadata is populated without duplicate imports."""

    _clear_models_aliases()

    models_pkg = importlib.import_module("app.models")
    models_path = Path(models_pkg.__file__).parent

    ignore_names = {"__pycache__", "tests", "migrations", "alembic"}

    for module in pkgutil.iter_modules(models_pkg.__path__):
        if module.ispkg:
            continue

        if module.name in ignore_names or module.name.startswith("_"):
            continue

        module_name = f"app.models.{module.name}"
        if module_name in sys.modules:
            continue

        module_file = models_path / f"{module.name}.py"
        if module_file.name.startswith("."):
            continue

        importlib.import_module(module_name)


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


try:
    import_models_once()
except InvalidRequestError as exc:
    message = str(exc)
    table_name = None
    if "already defined" in message:
        parts = message.split("'")
        if len(parts) >= 2:
            table_name = parts[1]
    suspect_modules = [
        name
        for name in sys.modules
        if any(token in name for token in ("limits", "client_group", "client_groups"))
    ]
    models_aliases = [name for name in sys.modules if name == "models" or name.startswith("models.")]
    logger.error(
        "Model import failed due to duplicate table%s. Table: %s. suspect modules: %s. models aliases: %s",
        "" if table_name else "s",
        table_name or "unknown",
        suspect_modules,
        models_aliases,
    )
    raise

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
        try:
            db_info = connection.exec_driver_sql(
                """
                SELECT
                    current_database(),
                    current_user,
                    current_schema(),
                    inet_server_addr(),
                    inet_server_port(),
                    version()
                """
            ).first()
        except Exception as exc:  # pragma: no cover - diagnostic only
            logger.warning("Could not fetch connection diagnostics: %s", exc)
        else:
            logger.info(
                "Connected to database=%s user=%s schema=%s host=%s port=%s version=%s",
                db_info[0],
                db_info[1],
                db_info[2],
                db_info[3],
                db_info[4],
                db_info[5],
            )

        migration_context = MigrationContext.configure(
            connection,
            opts={
                "version_table": "alembic_version",
                "version_table_schema": "public",
                "version_table_column_type": sa.String(length=128),
            },
        )

        migration_context._ensure_version_table()

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
        table_count = connection.exec_driver_sql(
            "select count(*) from pg_tables where schemaname='public'"
        ).scalar()

        logger.info(
            "Post-migration checks: alembic_version=%s, public tables=%s",
            version_exists,
            table_count,
        )

        if version_exists is None:
            raise RuntimeError(
                "Alembic finished without creating public.alembic_version. "
                "DDL did not apply — check transaction, schema, or engine configuration."
            )


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

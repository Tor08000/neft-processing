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
from app.diagnostics.db_state import log_connection_fingerprint, to_regclass  # noqa: E402

logger = logging.getLogger(__name__)
DEBUG_SQL = os.getenv("DB_DEBUG_SQL") == "1"
EVENT_LOGGER = logging.getLogger("app.alembic.sql")

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

    if DEBUG_SQL:
        logger.info("DB_DEBUG_SQL=1: enabling SQLAlchemy echo for migrations")
        config.set_main_option("sqlalchemy.echo", "true")

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


def _log_transaction_event(event_name: str, connection: sa.engine.Connection) -> None:
    EVENT_LOGGER.info("Migration connection event: %s connection=%s", event_name.upper(), hex(id(connection)))


def _attach_transaction_logging(connectable: sa.engine.Engine) -> None:
    for name in ("begin", "commit", "rollback", "close"):
        sa.event.listen(connectable, name, lambda conn, *_args, _name=name: _log_transaction_event(_name, conn))


def _configure_connection(connection: sa.engine.Connection, target_schema: str) -> None:
    target_schema_escaped = target_schema.replace('"', '""')
    search_path_sql = f"SET search_path TO \"{target_schema_escaped}\", public"
    connection.exec_driver_sql(search_path_sql)
    logger.info("Set search_path for migrations to %s", search_path_sql.removeprefix("SET search_path TO "))


def _log_schema_inventory(connection: sa.engine.Connection, *, label: str) -> None:
    logger.info("[%s] DB_SCHEMA setting: %s", label, DB_SCHEMA or "public")

    db_addr, db_port, db_name, db_user, db_schema = connection.exec_driver_sql(
        "SELECT inet_server_addr(), inet_server_port(), current_database(), current_user, current_schema();",
    ).first()
    logger.info(
        "[%s] connected to db=%s user=%s schema=%s at %s:%s",
        label,
        db_name,
        db_user,
        db_schema,
        db_addr,
        db_port,
    )

    search_path = connection.exec_driver_sql("SHOW search_path").scalar_one()
    logger.info("[%s] effective search_path=%s", label, search_path)

    schemas = [
        row[0]
        for row in connection.exec_driver_sql(
            """
            select nspname
            from pg_namespace
            where nspname not in ('pg_catalog','information_schema','pg_toast')
            order by 1
            """
        )
    ]
    logger.info("[%s] user schemas: %s", label, schemas)

    tables = [
        f"{row.table_schema}.{row.table_name}"
        for row in connection.exec_driver_sql(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_schema not in ('pg_catalog','information_schema','pg_toast')
            order by 1,2
            """
        )
    ]
    logger.info("[%s] user tables (%d): %s", label, len(tables), tables)


def run_migrations_online() -> sa.engine.Engine:
    """Запуск миграций в online-режиме (с реальным подключением к БД)."""
    connectable = sa.engine_from_config(  # type: ignore[attr-defined]
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    _attach_transaction_logging(connectable)

    target_schema = DB_SCHEMA or "public"

    cmd_opts = getattr(config, "cmd_opts", None)
    invoked_command = getattr(cmd_opts, "cmd", None)
    should_verify = not context.is_offline_mode() and invoked_command == "upgrade"

    with connectable.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError(
                f"Alembic migrations require PostgreSQL engine, got '{connection.dialect.name}'",
            )

        _configure_connection(connection, target_schema)
        _log_schema_inventory(connection, label="pre-upgrade")
        log_connection_fingerprint(connection, schema=target_schema, label="pre-upgrade", emitter=logger.info)

        ensure_alembic_version_length(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
            transactional_ddl=False,
            transaction_per_migration=True,
            version_table="alembic_version",
            version_table_schema=target_schema,
            as_sql=False,
        )

        context.run_migrations()

    if should_verify:
        verify_flag = context.get_x_argument(as_dictionary=True).get("verify", "true")
        if str(verify_flag).lower() == "true":
            with connectable.connect() as connection:
                _configure_connection(connection, target_schema)

                version_reg = to_regclass(connection, target_schema, "alembic_version")
                operations_reg = to_regclass(connection, target_schema, "operations")

                current_search_path = connection.exec_driver_sql("SHOW search_path").scalar_one_or_none()

                if version_reg is None:
                    raise RuntimeError(
                        "Post-upgrade verification failed: alembic_version missing in "
                        f"schema '{target_schema}' (search_path={current_search_path})"
                    )
                if operations_reg is None:
                    raise RuntimeError(
                        "Post-upgrade verification failed: operations missing in "
                        f"schema '{target_schema}' (search_path={current_search_path})"
                    )

                logger.info(
                    "Post-upgrade regclass status: alembic_version=%s operations=%s",
                    version_reg,
                    operations_reg,
                )

                script_heads = context.script.get_heads()
                version_rows = connection.exec_driver_sql(
                    sa.text(f'SELECT version_num FROM "{target_schema}".alembic_version')
                ).fetchall()
                version_values = [row[0] for row in version_rows]

                if not version_values:
                    raise RuntimeError(
                        "Post-upgrade verification failed: alembic_version exists but contains no rows"
                    )

                if set(version_values) != set(script_heads):
                    raise RuntimeError(
                        "Post-upgrade verification failed: alembic_version contents do not match script heads "
                        f"(db={version_values}, heads={script_heads})"
                    )

                _log_schema_inventory(connection, label="post-upgrade")
                log_connection_fingerprint(
                    connection, schema=target_schema, label="post-upgrade", emitter=logger.info
                )

    return connectable


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    engine = run_migrations_online()

    with engine.connect() as c:
        exists = c.scalar(sa.text("select to_regclass('public.operations')"))
        if not exists:
            raise RuntimeError(
                "CRITICAL: migration rollback detected — core tables missing after Alembic run"
            )

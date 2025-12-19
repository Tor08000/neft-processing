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
from app.alembic.helpers import regclass  # noqa: E402
from app.alembic.utils import ensure_alembic_version_length  # noqa: E402
from app import models as _models  # noqa: F401  # E402: ensure models are registered
from app.diagnostics.db_state import (  # noqa: E402
    log_connection_fingerprint,
    log_identity_snapshot,
)

logger = logging.getLogger(__name__)
x_arguments = context.get_x_argument(as_dictionary=True)
DEBUG_SQL = os.getenv("DB_DEBUG_SQL") == "1" or str(x_arguments.get("debug_sql", "")).lower() in {
    "1",
    "true",
    "yes",
}
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
    config.set_main_option("sqlalchemy.echo", "true")

    safe_url = make_url(db_url).render_as_string(hide_password=True)
    logger.info("Using database URL for alembic: %s", safe_url)

    if DEBUG_SQL:
        logger.info("debug_sql flag enabled: forcing SQLAlchemy echo and detailed transaction logging")

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


def _get_backend_pid(connection: sa.engine.Connection) -> int | None:
    raw = getattr(connection, "connection", None)
    driver_conn = getattr(raw, "driver_connection", None)
    pgconn = getattr(driver_conn, "pgconn", None)
    if pgconn is not None:
        return getattr(pgconn, "backend_pid", None)

    try:
        return connection.exec_driver_sql("select pg_backend_pid()").scalar_one_or_none()
    except Exception:  # noqa: BLE001 - best-effort diagnostics
        return None


def _log_transaction_event(event_name: str, connection: sa.engine.Connection) -> None:
    EVENT_LOGGER.info(
        "[tx] %s pid=%s connection=%s",
        event_name.upper(),
        _get_backend_pid(connection),
        hex(id(connection)),
    )


def _attach_transaction_logging(connectable: sa.engine.Engine) -> None:
    def _handler(name: str):
        def _wrapped(conn, *_args):  # type: ignore[override]
            _log_transaction_event(name, conn)

        return _wrapped

    for name in ("begin", "commit", "rollback"):
        sa.event.listen(connectable, name, _handler(name))


def _configure_connection(connection: sa.engine.Connection, target_schema: str) -> None:
    target_schema_escaped = target_schema.replace('"', '""')
    search_path_sql = f"SET search_path TO \"{target_schema_escaped}\", public"
    connection.exec_driver_sql(search_path_sql)
    logger.info("Set search_path for migrations to %s", search_path_sql.removeprefix("SET search_path TO "))


def _log_connection_identity(connection: sa.engine.Connection, *, label: str) -> None:
    db_name, db_user, db_addr, db_port, db_schema = connection.exec_driver_sql(
        "SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), current_schema();",
    ).one()
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
    logger.info("[%s] search_path=%s", label, search_path)


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


def _log_version_table_state(connection: sa.engine.Connection, target_schema: str, *, label: str) -> None:
    db_name, db_user = connection.exec_driver_sql("SELECT current_database(), current_user").one()
    search_path = connection.exec_driver_sql("SHOW search_path").scalar_one_or_none()
    version_reg = regclass(connection, f"{target_schema}.alembic_version")
    operations_reg = regclass(connection, f"{target_schema}.operations")
    version_schemas = _version_table_schemas(connection)
    logger.info(
        "[%s] version tables probe: db=%s user=%s search_path=%s alembic_version=%s operations=%s locations=%s",
        label,
        db_name,
        db_user,
        search_path,
        version_reg,
        operations_reg,
        version_schemas,
    )


def _log_missing_version_table_diagnostics(connection: sa.engine.Connection, target_schema: str) -> None:
    logger.error(
        "Detected operations table without alembic_version in schema '%s'; collecting diagnostics",
        target_schema,
    )
    operations_reg = regclass(connection, f"{target_schema}.operations")
    version_reg = regclass(connection, f"{target_schema}.alembic_version")
    logger.error("to_regclass operations=%s alembic_version=%s", operations_reg, version_reg)

    diagnostics: list[tuple[str, Any]] = []
    diagnostics.append(
        ("current_database,current_user", connection.exec_driver_sql("SELECT current_database(), current_user").one())
    )
    diagnostics.append(("search_path", connection.exec_driver_sql("SHOW search_path").scalar_one_or_none()))
    diagnostics.append(
        (
            "namespaces",
            connection.exec_driver_sql(
                """
                select nspname
                from pg_namespace
                where nspname not like 'pg_%' and nspname <> 'information_schema'
                order by 1
                """
            ).fetchall(),
        )
    )
    diagnostics.append(
        (
            "alembic_version tables",
            _version_table_schemas(connection),
        )
    )
    diagnostics.append(
        (
            "operations tables",
            connection.exec_driver_sql(
                "select table_schema, table_name from information_schema.tables where table_name='operations'"
            ).fetchall(),
        )
    )
    diagnostics.append(
        (
            "pg_class entries",
            connection.exec_driver_sql(
                """
                select relname, nspname
                from pg_class
                join pg_namespace on pg_class.relnamespace = pg_namespace.oid
                where relname in ('alembic_version','operations')
                order by relname, nspname
                """
            ).fetchall(),
        )
    )

    for name, value in diagnostics:
        logger.error("[diagnostics] %s: %s", name, value)


def _schema_table_count(connection: sa.engine.Connection, target_schema: str) -> int:
    return connection.execute(
        sa.text("select count(*) from information_schema.tables where table_schema=:schema"),
        {"schema": target_schema},
    ).scalar_one()


def _version_table_schemas(connection: sa.engine.Connection) -> list[str]:
    return list(
        connection.execute(
            sa.text(
                """
                select table_schema
                from information_schema.tables
                where table_name='alembic_version'
                order by table_schema
                """
            )
        ).scalars()
    )


def _require_version_table_in_target(
    connection: sa.engine.Connection, target_schema: str
) -> tuple[bool, list[str]]:
    version_schemas = _version_table_schemas(connection)
    if target_schema in version_schemas:
        return True, version_schemas

    if version_schemas:
        logger.error(
            "alembic_version located outside target schema '%s': %s",
            target_schema,
            version_schemas,
        )
        raise RuntimeError(
            f"alembic_version found in wrong schema(s): {version_schemas}; expected '{target_schema}'"
        )

    return False, version_schemas


def run_migrations_online() -> sa.engine.Engine:
    """Запуск миграций в online-режиме (с реальным подключением к БД)."""
    connectable = sa.engine_from_config(  # type: ignore[attr-defined]
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    _attach_transaction_logging(connectable)

    if DEBUG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        EVENT_LOGGER.setLevel(logging.INFO)

    target_schema = os.getenv("NEFT_DB_SCHEMA") or os.getenv("DB_SCHEMA") or "public"
    logger.info(
        "Alembic target schema resolved: %s (NEFT_DB_SCHEMA/DB_SCHEMA, default=public)", target_schema
    )

    cmd_opts = getattr(config, "cmd_opts", None)
    invoked_command = getattr(cmd_opts, "cmd", None)
    should_verify = not context.is_offline_mode() and invoked_command == "upgrade"
    script_heads = context.script.get_heads()

    with connectable.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError(
                f"Alembic migrations require PostgreSQL engine, got '{connection.dialect.name}'",
            )

        _log_connection_identity(connection, label="initial")
        _configure_connection(connection, target_schema)
        log_identity_snapshot(connection, schema=target_schema, label="alembic identity pre")
        _log_schema_inventory(connection, label="pre-upgrade")
        log_connection_fingerprint(connection, schema=target_schema, label="pre-upgrade", emitter=logger.info)

        txid_before = connection.exec_driver_sql("select txid_current(), pg_backend_pid();").one()
        logger.info("[tx-probe] before migrations: txid=%s pid=%s", *txid_before)

        ensure_alembic_version_length(connection)

        _log_version_table_state(connection, target_schema, label="pre-migrations")

        print("[alembic] version_table_schema=", target_schema, flush=True)
        print("[alembic] version_table=", "alembic_version", flush=True)
        print("[alembic] include_schemas=", True, flush=True)
        print("[alembic] dialect=", connection.dialect.name, flush=True)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            as_sql=False,
            include_schemas=True,
            compare_type=True,
            compare_server_default=True,
            version_table="alembic_version",
            version_table_schema=target_schema,
        )

        with context.begin_transaction():
            txid_inside = connection.exec_driver_sql("select txid_current(), pg_backend_pid();").one()
            logger.info("[tx-probe] inside transaction: txid=%s pid=%s", *txid_inside)
            context.run_migrations()
            ops_reg = regclass(connection, f"{target_schema}.operations")
            ver_reg = regclass(connection, f"{target_schema}.alembic_version")
            logger.info(
                "[ddl-visibility] same connection regclass: operations=%s alembic_version=%s",
                ops_reg,
                ver_reg,
            )
        log_identity_snapshot(connection, schema=target_schema, label="alembic identity post")

        txid_after = connection.exec_driver_sql("select txid_current(), pg_backend_pid();").one()
        logger.info("[tx-probe] after migrations (post-commit): txid=%s pid=%s", *txid_after)
        ops_reg = regclass(connection, f"{target_schema}.operations")
        ver_reg = regclass(connection, f"{target_schema}.alembic_version")
        logger.info(
            "[ddl-visibility] same connection after commit regclass: operations=%s alembic_version=%s",
            ops_reg,
            ver_reg,
        )

    with connectable.connect() as visibility_connection:
        _configure_connection(visibility_connection, target_schema)
        ops_reg = regclass(visibility_connection, f"{target_schema}.operations")
        ver_reg = regclass(visibility_connection, f"{target_schema}.alembic_version")
        logger.info(
            "[ddl-visibility] new connection regclass: operations=%s alembic_version=%s",
            ops_reg,
            ver_reg,
        )

    verify_flag = context.get_x_argument(as_dictionary=True).get("verify", "true")
    with connectable.connect() as connection:
        _configure_connection(connection, target_schema)
        _log_version_table_state(connection, target_schema, label="post-migrations")

        operations_reg = regclass(connection, f"{target_schema}.operations")
        version_reg = regclass(connection, f"{target_schema}.alembic_version")
        version_present_in_target, version_schemas = _require_version_table_in_target(connection, target_schema)
        table_count = _schema_table_count(connection, target_schema)
        logger.info(
            "Post-migrations table count in schema '%s': %s", target_schema, table_count
        )

        missing_version_table = operations_reg is not None and not version_present_in_target
        if missing_version_table:
            _log_missing_version_table_diagnostics(connection, target_schema)

        if missing_version_table:
            raise RuntimeError(
                "CRITICAL: operations exists but alembic_version is missing; version table config is broken"
            )

        if should_verify and str(verify_flag).lower() == "true":
            _log_connection_identity(connection, label="post-upgrade")

            current_search_path = connection.exec_driver_sql("SHOW search_path").scalar_one_or_none()

            if not version_present_in_target:
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

            version_rows = connection.execute(
                sa.text(f'SELECT version_num FROM \"{target_schema}\".alembic_version')
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
            log_connection_fingerprint(connection, schema=target_schema, label="post-upgrade", emitter=logger.info)

    return connectable


if os.getenv("ALEMBIC_SKIP_RUN"):
    logger.info("ALEMBIC_SKIP_RUN is set; skipping Alembic execution")
elif context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from __future__ import annotations

"""Database connection diagnostics shared between entrypoints and tests."""

import contextlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DB_SCHEMA, DB_SCHEMA_SOURCE, DATABASE_URL, schema_resolution_line

USER_SCHEMA_FILTER = "('pg_catalog','information_schema','pg_toast')"


@dataclass(frozen=True)
class ConnectionInventory:
    """Snapshot of the current database connection state."""

    server_addr: str | None
    server_port: int | None
    current_database: str | None
    current_user: str | None
    search_path: str | None
    schemas: list[str]
    tables: list[tuple[str, str]]
    alembic_versions: list[str]
    schema: str

    def missing_tables(self, required: Iterable[str] = REQUIRED_CORE_TABLES) -> list[str]:
        existing = {table_name for table_schema, table_name in self.tables if table_schema == self.schema}
        return sorted(set(required) - existing)


@dataclass(frozen=True)
class IdentitySnapshot:
    """Physical database identity fingerprint."""

    server_addr: str | None
    server_port: int | None
    current_database: str | None
    current_user: str | None
    current_schema: str | None
    search_path: str | None
    backend_pid: int | None
    database_oid: int | None
    postmaster_start_time: datetime | None


def to_regclass(connection: Connection, schema: str, name: str) -> str | None:
    """Return the regclass for the given schema-qualified name, if it exists."""

    schema_name = schema or "public"
    regclass = f"{schema_name}.{name}"
    return connection.execute(text("select to_regclass(:reg)"), {"reg": regclass}).scalar_one_or_none()


def _make_engine(url: str = DATABASE_URL, schema: str = DB_SCHEMA) -> Engine:
    debug_sql = os.getenv("DB_DEBUG_SQL") == "1"
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
        "echo": debug_sql,
    }

    if url.startswith("postgresql"):
        # Keep the requested schema at the front of the search_path for every
        # connection created via this Engine.
        engine_kwargs["connect_args"] = {
            "options": f"-csearch_path={schema},public",
            "prepare_threshold": 0,
        }
    engine = create_engine(url, **engine_kwargs)

    if debug_sql:
        _attach_transaction_logging(engine)

    return engine


def _attach_transaction_logging(engine: Engine) -> None:
    logger = logging.getLogger("app.db_debug.sql")

    def _log(event_name: str):
        def _handler(conn, *_):  # type: ignore[override]
            logger.info("[db-debug] %s connection=%s", event_name.upper(), hex(id(conn)))

        return _handler

    for name in ("begin", "commit", "rollback"):
        event.listen(engine, name, _log(name))


def collect_inventory(url: str = DATABASE_URL, schema: str = DB_SCHEMA) -> ConnectionInventory:
    engine = _make_engine(url=url, schema=schema)

    with engine.connect() as conn:
        logger = logging.getLogger(__name__)
        logger.info(schema_resolution_line(schema, DB_SCHEMA_SOURCE))
        # Ensure the connection uses the same schema the application expects.
        with contextlib.suppress(Exception):
            conn.execute(text(f'SET search_path TO "{schema}", public'))

        server_addr, server_port, current_db, current_user = conn.execute(
            text(
                "SELECT inet_server_addr(), inet_server_port(), current_database(), current_user"
            )
        ).one()

        search_path = conn.execute(text("SHOW search_path")).scalar_one_or_none()

        schemas = [
            row[0]
            for row in conn.execute(
                text(
                    f"""
                    select nspname
                    from pg_namespace
                    where nspname not in {USER_SCHEMA_FILTER}
                    order by 1
                    """
                )
            )
        ]

        tables = [
            (row.table_schema, row.table_name)
            for row in conn.execute(
                text(
                    f"""
                    select table_schema, table_name
                    from information_schema.tables
                    where table_schema not in {USER_SCHEMA_FILTER}
                    order by 1,2
                    """
                )
            )
        ]

        alembic_versions: list[str] = []
        reg = to_regclass(conn, schema, "alembic_version")
        if reg:
            alembic_versions = [
                row[0] for row in conn.execute(text(f'SELECT version_num FROM "{schema}".alembic_version'))
            ]

    return ConnectionInventory(
        server_addr=server_addr,
        server_port=server_port,
        current_database=current_db,
        current_user=current_user,
        search_path=search_path,
        schemas=schemas,
        tables=tables,
        alembic_versions=alembic_versions,
        schema=schema,
    )


def _emit(prefix: str, message: str, *, emitter: Callable[[str], None] | None = None) -> None:
    logger_func = emitter or logging.getLogger(__name__).info
    logger_func(f"{prefix} {message}")


def _safe_scalar(connection: Connection, sql: str, params: dict | None = None):
    return connection.execute(text(sql), params or {}).scalar_one_or_none()


def _collect_identity_probe_fields(connection: Connection, schema: str) -> tuple:
    schema_name = schema or "public"

    server_addr, server_port, current_db, current_user = connection.execute(
        text("select inet_server_addr(), inet_server_port(), current_database(), current_user")
    ).one()
    database_oid = connection.execute(
        text("select oid from pg_database where datname=current_database();")
    ).scalar_one_or_none()
    postmaster_start = connection.execute(text("select pg_postmaster_start_time();")).scalar_one_or_none()
    table_count = connection.execute(
        text("select count(*) from information_schema.tables where table_schema=:schema"),
        {"schema": schema_name},
    ).scalar_one()

    return (
        server_addr,
        server_port,
        current_db,
        current_user,
        database_oid,
        postmaster_start,
        schema_name,
        table_count,
    )


def identity_probe_line(connection: Connection, *, schema: str, label: str | None = None) -> str:
    """Render a single-line DB identity probe with server and table counts."""

    (
        server_addr,
        server_port,
        current_db,
        current_user,
        database_oid,
        postmaster_start,
        schema_name,
        table_count,
    ) = _collect_identity_probe_fields(connection, schema)

    prefix = f"DB_ID{f'[{label}]' if label else ''}"
    return (
        f"{prefix}: host={server_addr} port={server_port} db={current_db} user={current_user} "
        f"db_oid={database_oid} postmaster_start={postmaster_start} schema={schema_name} "
        f"table_count={table_count}"
    )


def collect_identity_snapshot(connection: Connection) -> IdentitySnapshot:
    """Collect a deterministic fingerprint of the active connection."""

    server_addr, server_port = connection.execute(
        text("select inet_server_addr(), inet_server_port();")
    ).one()
    current_database, current_user = connection.execute(
        text("select current_database(), current_user;")
    ).one()
    current_schema, search_path = connection.execute(
        text("select current_schema, current_setting('search_path');")
    ).one()
    backend_pid = _safe_scalar(connection, "select pg_backend_pid();")
    database_oid = _safe_scalar(
        connection,
        "select oid from pg_database where datname=current_database();",
    )
    postmaster_start_time = _safe_scalar(connection, "select pg_postmaster_start_time();")

    return IdentitySnapshot(
        server_addr=server_addr,
        server_port=server_port,
        current_database=current_database,
        current_user=current_user,
        current_schema=current_schema,
        search_path=search_path,
        backend_pid=backend_pid,
        database_oid=database_oid,
        postmaster_start_time=postmaster_start_time,
    )


def log_identity_snapshot(
    connection: Connection,
    *,
    schema: str = DB_SCHEMA,
    emitter: Callable[[str], None] | None = None,
    label: str | None = None,
) -> IdentitySnapshot:
    """Collect and log a DB identity fingerprint."""

    snapshot = collect_identity_snapshot(connection)
    prefix = f"[{label or 'db-identity'}]"
    _emit(
        prefix,
        (
            f"server={snapshot.server_addr}:{snapshot.server_port} "
            f"db={snapshot.current_database} user={snapshot.current_user} "
            f"schema={snapshot.current_schema} search_path={snapshot.search_path} "
            f"target_schema={schema or 'public'}"
        ),
        emitter=emitter,
    )
    _emit(
        prefix,
        (
            f"database_oid={snapshot.database_oid} backend_pid={snapshot.backend_pid} "
            f"postmaster_start_time={snapshot.postmaster_start_time}"
        ),
        emitter=emitter,
    )
    return snapshot


def log_connection_fingerprint(
    connection: Connection,
    *,
    schema: str = DB_SCHEMA,
    emitter: Callable[[str], None] | None = None,
    label: str | None = None,
) -> None:
    """Log a detailed DB fingerprint using a single connection."""

    prefix = f"[db-fingerprint{f' {label}' if label else ''}]"

    server_addr, server_port, current_db, current_user, current_schema = connection.execute(
        text(
            "SELECT inet_server_addr(), inet_server_port(), current_database(), current_user, current_schema()",
        ),
    ).one()
    search_path = _safe_scalar(connection, "SHOW search_path")
    version_str = _safe_scalar(connection, "SELECT version()")

    _emit(
        prefix,
        (
            f"server={server_addr}:{server_port} db={current_db} user={current_user} "
            f"current_schema={current_schema} search_path={search_path} target_schema={schema or 'public'}"
        ),
        emitter=emitter,
    )
    _emit(prefix, f"version={version_str}", emitter=emitter)

    db_info = connection.execute(
        text("SELECT datname, oid FROM pg_database WHERE datname = current_database()"),
    ).one_or_none()
    if db_info:
        _emit(prefix, f"database_oid={db_info.oid}", emitter=emitter)

    txid = _safe_scalar(connection, "SELECT txid_current()")
    now = _safe_scalar(connection, "SELECT now()")
    _emit(prefix, f"txid_current={txid} now={now}", emitter=emitter)

    target_schema = schema or "public"
    alembic_reg = to_regclass(connection, target_schema, "alembic_version")
    operations_reg = to_regclass(connection, target_schema, "operations")
    _emit(prefix, f"alembic_version_regclass={alembic_reg} operations_regclass={operations_reg}", emitter=emitter)

    user_schemas = [
        row[0]
        for row in connection.execute(
            text(
                f"""
                select nspname
                from pg_namespace
                where nspname not in {USER_SCHEMA_FILTER}
                order by 1
                """
            )
        )
    ]
    _emit(prefix, f"user_schemas={user_schemas}", emitter=emitter)

    tables = connection.execute(
        text(
            f"""
            select table_schema, table_name
            from information_schema.tables
            where table_schema not in {USER_SCHEMA_FILTER}
            order by 1,2
            """
        )
    ).all()
    formatted_tables = [f"{row.table_schema}.{row.table_name}" for row in tables]
    _emit(prefix, f"user_table_count={len(formatted_tables)}", emitter=emitter)
    _emit(prefix, f"user_tables={formatted_tables}", emitter=emitter)


def log_fingerprint_from_url(
    url: str = DATABASE_URL,
    *,
    schema: str = DB_SCHEMA,
    emitter: Callable[[str], None] | None = None,
    label: str | None = None,
) -> None:
    engine = _make_engine(url=url, schema=schema)
    with engine.connect() as conn:
        log_connection_fingerprint(conn, schema=schema, emitter=emitter, label=label)


def log_identity_from_url(
    url: str = DATABASE_URL,
    *,
    schema: str = DB_SCHEMA,
    emitter: Callable[[str], None] | None = None,
    label: str | None = None,
) -> IdentitySnapshot:
    engine = _make_engine(url=url, schema=schema)
    with engine.connect() as conn:
        return log_identity_snapshot(conn, schema=schema, emitter=emitter, label=label)


def log_identity_probe_from_url(
    url: str = DATABASE_URL,
    *,
    schema: str = DB_SCHEMA,
    emitter: Callable[[str], None] | None = None,
    label: str | None = None,
) -> str:
    """Emit a single-line DB identity probe for a URL and return the line."""

    engine = _make_engine(url=url, schema=schema)
    with engine.connect() as conn:
        line = identity_probe_line(conn, schema=schema, label=label)
        output = emitter or (lambda msg: print(msg, flush=True))
        output(line)
        return line

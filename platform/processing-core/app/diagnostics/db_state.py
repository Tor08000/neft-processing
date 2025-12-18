from __future__ import annotations

"""Database connection diagnostics shared between entrypoints and tests."""

import contextlib
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DB_SCHEMA, DATABASE_URL


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


def _make_engine(url: str = DATABASE_URL, schema: str = DB_SCHEMA) -> Engine:
    engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}

    if url.startswith("postgresql"):
        # Keep the requested schema at the front of the search_path for every
        # connection created via this Engine.
        engine_kwargs["connect_args"] = {"options": f"-csearch_path={schema},public"}

    return create_engine(url, **engine_kwargs)


def collect_inventory(url: str = DATABASE_URL, schema: str = DB_SCHEMA) -> ConnectionInventory:
    engine = _make_engine(url=url, schema=schema)

    with engine.connect() as conn:
        # Ensure the connection uses the same schema the application expects.
        with contextlib.suppress(Exception):
            conn.execute(text(f'SET search_path TO "{schema}", public'))

        server_addr, server_port, current_db, current_user = conn.execute(
            text(
                "SELECT inet_server_addr(), inet_server_port(), current_database(), current_user"
            )
        ).one()

        search_path = conn.execute(text("SHOW search_path")).scalar_one_or_none()

        schemas = [row[0] for row in conn.execute(text("SELECT nspname FROM pg_namespace ORDER BY 1"))]

        tables = [
            (row.table_schema, row.table_name)
            for row in conn.execute(
                text(
                    """
                    select table_schema, table_name
                    from information_schema.tables
                    where table_type='BASE TABLE'
                    order by 1,2
                    """
                )
            )
        ]

        alembic_versions: list[str] = []
        reg = conn.execute(
            text("SELECT to_regclass(:reg) AS reg"), {"reg": f"{schema}.alembic_version"}
        ).scalar()
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


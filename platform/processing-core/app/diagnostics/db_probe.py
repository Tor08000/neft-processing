from __future__ import annotations

import json
from typing import Any, Dict

from sqlalchemy import text

from app.db import engine
from app.db.schema import SCHEMA_RESOLUTION

PROBE_TABLE = f'"{SCHEMA_RESOLUTION.schema}"._probe_migrations'


def _collect_fingerprint(connection) -> Dict[str, Any]:
    return connection.execute(
        text(
            """
            SELECT
                current_database() AS current_database,
                current_user AS current_user,
                inet_server_addr() AS inet_server_addr,
                inet_server_port() AS inet_server_port,
                pg_postmaster_start_time() AS pg_postmaster_start_time,
                version() AS version,
                current_setting('data_directory') AS data_directory,
                oid AS database_oid
            FROM pg_database
            WHERE datname = current_database()
            """
        )
    ).mappings().one()


def run_probe() -> Dict[str, Any]:
    """Create the probe table and report its presence and DB fingerprint."""

    with engine.begin() as connection:
        print(f"[db_probe] {SCHEMA_RESOLUTION.line()}")
        connection.execute(text(f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE} (x INT)"))
        regclass = connection.execute(
            text("SELECT to_regclass(:name)"),
            {"name": f"{SCHEMA_RESOLUTION.schema}._probe_migrations"},
        ).scalar_one_or_none()

        fingerprint = {key: str(value) for key, value in _collect_fingerprint(connection).items()}
        table_count = connection.execute(
            text(
                """
                select count(*)
                from information_schema.tables
                where table_schema = :schema
            """
        ),
        {"schema": SCHEMA_RESOLUTION.schema},
    ).scalar_one()

    return {
        "source": "core-api",
        "regclass": regclass,
        "fingerprint": fingerprint,
        "schema": SCHEMA_RESOLUTION.line(),
        "table_count": table_count,
    }


if __name__ == "__main__":
    print(json.dumps(run_probe()))

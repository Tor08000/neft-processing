from __future__ import annotations

import json
from typing import Any, Dict

from sqlalchemy import text

from app.db import engine

PROBE_TABLE = "public._probe_migrations"


def _collect_fingerprint(connection) -> Dict[str, Any]:
    row = connection.execute(
        text(
            """
            SELECT
                current_database() AS current_database,
                current_user AS current_user,
                inet_server_addr() AS inet_server_addr,
                inet_server_port() AS inet_server_port,
                pg_postmaster_start_time() AS pg_postmaster_start_time,
                version() AS version,
                current_setting('data_directory') AS data_directory
            """
        )
    ).mappings().one()

    return {key: str(value) for key, value in row.items()}


def run_probe() -> Dict[str, Any]:
    """Create the probe table and report its presence and DB fingerprint."""

    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE} (x INT)"
        )
        regclass = connection.exec_driver_sql(
            "SELECT to_regclass('public._probe_migrations')"
        ).scalar()

        fingerprint = _collect_fingerprint(connection)

    return {"source": "core-api", "regclass": regclass, "fingerprint": fingerprint}


if __name__ == "__main__":
    print(json.dumps(run_probe()))

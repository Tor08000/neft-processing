from __future__ import annotations

import os

import sqlalchemy as sa
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

VERSION_TABLE_NAME = "alembic_version_core"
VERSION_TABLE_SCHEMA = "processing_core"



def _read_version_rows(connection: sa.Connection) -> list[str]:
    quoted_schema = VERSION_TABLE_SCHEMA.replace('"', '""')
    return (
        connection.execute(
            sa.text(f'SELECT version_num FROM "{quoted_schema}".{VERSION_TABLE_NAME} ORDER BY version_num')
        )
        .scalars()
        .all()
    )


def _read_ctx_heads(connection: sa.Connection) -> list[str]:
    context = MigrationContext.configure(
        connection,
        opts={"version_table": VERSION_TABLE_NAME, "version_table_schema": VERSION_TABLE_SCHEMA},
    )
    return sorted(context.get_current_heads())


def run_upgrade_preflight() -> None:
    database_url = os.getenv("DATABASE_URL")
    alembic_config_path = os.getenv("ALEMBIC_CONFIG", "/app/app/alembic.ini")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    config = Config(alembic_config_path)
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("version_table", VERSION_TABLE_NAME)
    config.set_main_option("version_table_schema", VERSION_TABLE_SCHEMA)
    script = ScriptDirectory.from_config(config)
    script_heads = sorted(script.get_heads())

    engine = sa.create_engine(database_url)
    quoted_schema = VERSION_TABLE_SCHEMA.replace('"', '""')

    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'))
            connection.execute(
                sa.text(
                    f'CREATE TABLE IF NOT EXISTS "{quoted_schema}".{VERSION_TABLE_NAME} '
                    '(version_num VARCHAR(128) NOT NULL PRIMARY KEY)'
                )
            )

        with engine.connect() as connection:
            sql_current_rows = _read_version_rows(connection)
            ctx_current_rows = _read_ctx_heads(connection)

        sql_current = ",".join(sql_current_rows) if sql_current_rows else "<base>"
        print(f"[entrypoint] sql_current={sql_current}", flush=True)
        print(f"[entrypoint] script_heads={script_heads}", flush=True)
        print("[entrypoint] upgrade plan: from sql_current to head", flush=True)

        if sql_current_rows != ctx_current_rows:
            raise RuntimeError(
                "refusing upgrade: alembic version mismatch before upgrade "
                f"(sql_current={sql_current_rows}, ctx_current={ctx_current_rows}). "
                "Reset DB or run alembic stamp manually outside migrations for recovery."
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_upgrade_preflight()

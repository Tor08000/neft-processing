from __future__ import annotations

import os

import sqlalchemy as sa
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

VERSION_TABLE_NAME = "alembic_version_core"
VERSION_TABLE_SCHEMA = "processing_core"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _replace_versions(connection: sa.Connection, revisions: list[str]) -> None:
    quoted_schema = VERSION_TABLE_SCHEMA.replace('"', '""')
    connection.execute(sa.text(f'TRUNCATE TABLE "{quoted_schema}".{VERSION_TABLE_NAME}'))
    for revision in revisions:
        connection.execute(
            sa.text(f'INSERT INTO "{quoted_schema}".{VERSION_TABLE_NAME}(version_num) VALUES (:revision)'),
            {"revision": revision},
        )


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
            if not _env_flag("DEV_ALLOW_VERSION_FORCE", False):
                raise RuntimeError(
                    "refusing upgrade: alembic version mismatch before upgrade "
                    f"(sql_current={sql_current_rows}, ctx_current={ctx_current_rows}). "
                    "Set DEV_ALLOW_VERSION_FORCE=1 only for local/dev recovery."
                )

            with engine.begin() as connection:
                _replace_versions(connection, sql_current_rows)

            with engine.connect() as connection:
                ctx_after_force = _read_ctx_heads(connection)

            if sql_current_rows != ctx_after_force:
                raise RuntimeError(
                    "DEV_ALLOW_VERSION_FORCE=1 could not reconcile alembic version state "
                    f"(sql_current={sql_current_rows}, ctx_after_force={ctx_after_force}). "
                    "Reset DB is recommended."
                )
            print(
                "[entrypoint] dev-force: reconciled alembic version table to sql_current before upgrade",
                flush=True,
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_upgrade_preflight()

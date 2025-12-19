from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

from app.db.schema import resolve_db_schema

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

schema_resolution = resolve_db_schema()
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
<<<<<<< HEAD
    # В этом проекте оффлайн-миграции обычно не нужны.
    # Лучше явно запретить, чтобы не было тихих сюрпризов.
    raise RuntimeError("Offline migrations are not supported. Use online migrations.")
=======
    msg = "Offline migrations are not supported; provide DATABASE_URL for online run."
    raise RuntimeError(msg)


def _configure(connection) -> None:
    connection.execute(text(schema_resolution.search_path_sql))
    context.configure(
        connection=connection,
        version_table_schema=schema_resolution.schema,
        include_schemas=True,
        transaction_per_migration=True,
    )
>>>>>>> 05bac1164a8f703cbc45e8dbc8c404cad85192ae


def run_migrations_online() -> None:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        connect_args={
            "options": f"-c search_path={schema_resolution.schema}",
            "prepare_threshold": 0,
        },
    )

    with engine.connect() as connection:
        # ВАЖНО: не стартуем implicit transaction до Alembic.
        # Иначе на выходе получишь ROLLBACK и “tables missing”.
        connection = connection.execution_options(isolation_level="AUTOCOMMIT")

        # search_path фиксируем явно
        connection.execute(text(schema_resolution.search_path_sql))

        context.configure(
            connection=connection,
            version_table_schema=schema_resolution.schema,
            include_schemas=True,
            transaction_per_migration=True,
        )

        context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

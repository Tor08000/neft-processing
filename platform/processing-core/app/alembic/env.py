from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.db import Base  # type: ignore  # noqa: E402
from app.db.schema import resolve_db_schema  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError("DATABASE_URL is required for alembic migrations") from exc

config.set_main_option("sqlalchemy.url", DATABASE_URL)

schema_resolution = resolve_db_schema()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    msg = "Offline migrations are not supported; provide DATABASE_URL for online run."
    raise RuntimeError(msg)


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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema_resolution.schema,
            include_schemas=True,
            transactional_ddl=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool


def _build_database_url() -> str:
    return (
        os.getenv("AUTH_DB_DSN")
        or os.getenv("DATABASE_URL")
        or (
            "postgresql://{user}:{password}@{host}:{port}/{db}".format(
                user=os.getenv("POSTGRES_USER", "neft"),
                password=os.getenv("POSTGRES_PASSWORD", "neft"),
                host=os.getenv("POSTGRES_HOST", "postgres"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                db=os.getenv("POSTGRES_DB", "neft"),
            )
        )
    )


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


config = context.config
target_metadata = None

database_url = config.get_main_option("sqlalchemy.url") or _build_database_url()
database_url = _normalize_database_url(database_url)
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        transactional_ddl=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            transactional_ddl=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

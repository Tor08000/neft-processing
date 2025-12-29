from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def make_sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def run_auth_migrations(database_url: str) -> None:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    alembic_cfg.set_main_option("script_location", str(config_path.parent / "app" / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", make_sync_database_url(database_url))
    command.upgrade(alembic_cfg, "head")

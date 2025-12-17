import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import engine


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Smoke test requires Postgres")
def test_bootstrap_schema_creates_tables():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL is not configured")

    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    connectable = sa.create_engine(db_url)
    try:
        with connectable.connect() as connection:
            connection.exec_driver_sql("select 1")
    except sa.exc.OperationalError as exc:  # pragma: no cover - diagnostic skip
        pytest.skip(f"Postgres is not available: {exc}")

    command.upgrade(cfg, "20270601_0024_bootstrap_schema")

    with connectable.connect() as connection:
        merchants_exists = connection.exec_driver_sql(
            "select to_regclass('public.merchants')"
        ).scalar()
        version_exists = connection.exec_driver_sql(
            "select to_regclass('public.alembic_version')"
        ).scalar()

    assert merchants_exists, "Migration should create public.merchants"
    assert version_exists, "alembic_version should be created in public schema"

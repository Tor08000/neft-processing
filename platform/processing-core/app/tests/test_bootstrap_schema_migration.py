import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import engine


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Bootstrap test requires Postgres")
def test_bootstrap_migration_idempotent():
    config_path = Path(__file__).parent.parent / "alembic.ini"
    assert config_path.exists(), "alembic.ini not found"

    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

    command.upgrade(cfg, "head")

    with engine.connect() as connection:
        for table in ("merchants", "clients", "operations"):
            result = connection.exec_driver_sql(
                f"select to_regclass('public.{table}')"
            ).scalar()
            assert result, f"Missing table {table} after first upgrade"

        public_merchants = connection.exec_driver_sql(
            "select to_regclass('public.merchants')"
        ).scalar()
        assert public_merchants, "merchants should be created in public schema"

        neft_merchants = connection.exec_driver_sql(
            "select to_regclass('neft.merchants')"
        ).scalar()
        assert not neft_merchants, "merchants should not be created in neft schema"

    command.upgrade(cfg, "head")

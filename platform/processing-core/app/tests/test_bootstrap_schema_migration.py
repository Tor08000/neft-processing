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
            result = connection.execute(
                sa.text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table}"}
            ).scalar()
            assert result, f"Missing table {table} after first upgrade"

    command.upgrade(cfg, "head")

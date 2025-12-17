import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import engine


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Test requires Postgres")
def test_operations_table_has_required_columns():
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

    command.upgrade(cfg, "head")

    with connectable.connect() as connection:
        inspector = sa.inspect(connection)
        table_names = inspector.get_table_names(schema="public")
        assert "operations" in table_names, "operations table should be present"

        column_names = {
            column["name"] for column in inspector.get_columns("operations", schema="public")
        }

    assert "accounts" in column_names
    assert "posting_result" in column_names

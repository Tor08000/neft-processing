from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import engine
from app.db.schema import resolve_db_schema
from app.tests.utils import ensure_connectable, get_database_url


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Test requires Postgres")
def test_operations_table_has_required_columns():
    db_url = get_database_url()
    schema = resolve_db_schema().schema

    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    connectable = ensure_connectable(db_url)
    command.upgrade(cfg, "head")

    try:
        with connectable.connect() as connection:
            inspector = sa.inspect(connection)
            table_names = inspector.get_table_names(schema=schema)
            assert "operations" in table_names, "operations table should be present"

            column_names = {
                column["name"]
                for column in inspector.get_columns("operations", schema=schema)
            }
    finally:
        connectable.dispose()

    assert "accounts" in column_names
    assert "posting_result" in column_names

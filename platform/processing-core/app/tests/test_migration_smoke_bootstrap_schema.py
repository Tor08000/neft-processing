from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.db import DB_SCHEMA, engine
from app.tests.utils import ensure_connectable, get_database_url


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Smoke test requires Postgres")
def test_bootstrap_schema_creates_tables():
    db_url = get_database_url()

    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("sqlalchemy.url", db_url)

    connectable = ensure_connectable(db_url)
    command.upgrade(cfg, "20270601_0024_bootstrap_schema")

    try:
        with connectable.connect() as connection:
            merchants_exists = connection.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{DB_SCHEMA}.merchants"},
            ).scalar()
            version_exists = connection.execute(
                sa.text("select to_regclass(:reg)"),
                {"reg": f"{DB_SCHEMA}.alembic_version"},
            ).scalar()
    finally:
        connectable.dispose()

    assert merchants_exists, f"Migration should create {DB_SCHEMA}.merchants"
    assert version_exists, f"alembic_version should be created in {DB_SCHEMA} schema"

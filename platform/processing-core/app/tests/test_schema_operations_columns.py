from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from app.db import engine
from app.db.schema import resolve_db_schema
from app.models.operation import Operation
from app.tests.utils import ensure_connectable, get_database_url


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Schema check requires Postgres")
def test_operations_columns_available_and_queryable():
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
            column_names = {
                column["name"]
                for column in inspector.get_columns("operations", schema=schema)
            }

            assert "accounts" in column_names
            assert "posting_result" in column_names

            # Ensure the column can be selected without raising UndefinedColumn.
            connection.exec_driver_sql(
                f'select posting_result from "{schema}".operations limit 1'
            ).all()

        session_factory = sessionmaker(bind=connectable)
        with session_factory() as session:
            session.execute(sa.select(Operation.posting_result).limit(1)).all()
    finally:
        connectable.dispose()

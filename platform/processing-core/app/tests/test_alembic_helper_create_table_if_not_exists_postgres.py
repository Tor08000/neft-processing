import logging
import shutil
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.alembic import helpers
from app.db.schema import resolve_db_schema
from app.tests.utils import ensure_connectable, get_database_url

pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required for postgres tests")


def _override_create_table(conn: sa.Connection) -> None:
    def _create_table(name: str, *cols: sa.Column, schema: str | None = None, **kwargs) -> None:
        table = sa.Table(name, sa.MetaData(), *cols, schema=schema, **kwargs)
        table.create(bind=conn)

    setattr(conn, "op_override", SimpleNamespace(create_table=_create_table))


def test_create_table_if_not_exists_drops_orphan_type(caplog: pytest.LogCaptureFixture):
    db_url = get_database_url()
    if not db_url.startswith("postgresql"):
        pytest.skip("Postgres required for composite type regression test")

    engine = ensure_connectable(db_url)
    schema = resolve_db_schema().schema
    table_name = "client_onboarding_state"

    caplog.set_level(logging.WARNING, logger="app.alembic.helpers")
    with engine.begin() as conn:
        _override_create_table(conn)
        conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE')
        conn.exec_driver_sql(f'CREATE TYPE "{schema}"."{table_name}" AS (id integer)')
        assert not helpers.table_exists_real(conn, schema, table_name)
        assert helpers.type_entry_kind(conn, schema, table_name) == "c"

        helpers.create_table_if_not_exists(
            conn,
            table_name,
            schema=schema,
            columns=(
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

        assert helpers.table_exists(conn, table_name, schema=schema)
    assert any(
        "Dropping orphan type" in record.message and table_name in record.message
        for record in caplog.records
    )


def test_create_table_if_not_exists_recovers_from_orphan_type():
    db_url = get_database_url()
    if not db_url.startswith("postgresql"):
        pytest.skip("Postgres required for composite type regression test")

    engine = ensure_connectable(db_url)
    schema = resolve_db_schema().schema
    table_name = "client_onboarding_state"

    with engine.begin() as conn:
        _override_create_table(conn)
        conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE')
        conn.exec_driver_sql(f'CREATE TYPE "{schema}"."{table_name}" AS (id integer)')
        assert not helpers.table_exists_real(conn, schema, table_name)
        assert helpers.type_entry_kind(conn, schema, table_name) == "c"

        helpers.create_table_if_not_exists(
            conn,
            table_name,
            schema=schema,
            columns=(
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

        assert helpers.table_exists(conn, table_name, schema=schema)


def test_create_table_if_not_exists_drops_orphan_domain():
    db_url = get_database_url()
    if not db_url.startswith("postgresql"):
        pytest.skip("Postgres required for domain regression test")

    engine = ensure_connectable(db_url)
    schema = resolve_db_schema().schema
    table_name = "orphan_domain_table"

    with engine.begin() as conn:
        _override_create_table(conn)
        conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE')
        conn.exec_driver_sql(f'DROP DOMAIN IF EXISTS "{schema}"."{table_name}" CASCADE')
        conn.exec_driver_sql(f'CREATE DOMAIN "{schema}"."{table_name}" AS text')
        assert not helpers.table_exists_real(conn, schema, table_name)
        assert helpers.type_entry_kind(conn, schema, table_name) == "d"

        helpers.create_table_if_not_exists(
            conn,
            table_name,
            schema=schema,
            columns=(sa.Column("id", sa.Integer(), primary_key=True),),
        )

        assert helpers.table_exists(conn, table_name, schema=schema)
        assert helpers.type_entry_kind(conn, schema, table_name) == "c"

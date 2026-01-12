from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.alembic import helpers
from app.db.schema import resolve_db_schema
from app.models.crm import ClientOnboardingStateEnum
from app.tests.utils import ensure_connectable, get_database_url


def _override_create_table(conn: sa.Connection) -> None:
    def _create_table(name: str, *cols: sa.Column, schema: str | None = None, **kwargs) -> None:
        table = sa.Table(name, sa.MetaData(), *cols, schema=schema, **kwargs)
        table.create(bind=conn)

    setattr(conn, "op_override", SimpleNamespace(create_table=_create_table))


def test_create_table_if_not_exists_drops_orphan_composite_type():
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
        assert not helpers.table_exists(conn, table_name, schema=schema)
        assert helpers.composite_type_exists(conn, table_name, schema=schema)

        helpers.create_table_if_not_exists(
            conn,
            table_name,
            schema=schema,
            columns=(
                sa.Column(
                    "client_id",
                    sa.String(length=64),
                    sa.ForeignKey(f"{schema}.crm_clients.id"),
                    primary_key=True,
                ),
                sa.Column(
                    "state",
                    sa.Enum(
                        *(state.value for state in ClientOnboardingStateEnum),
                        name="client_onboarding_state",
                        native_enum=False,
                    ),
                    nullable=False,
                ),
                sa.Column("state_entered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
                sa.Column("block_reason", sa.Text()),
                sa.Column("meta", sa.JSON()),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )

        assert helpers.table_exists(conn, table_name, schema=schema)

from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _column_names(connection: sa.engine.Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    return {column["name"] for column in inspector.get_columns(table_name)}


def test_client_subscriptions_audit_event_id_migration_adds_missing_column():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "client_subscriptions",
        metadata,
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        assert "audit_event_id" not in _column_names(connection, "client_subscriptions")

        migration = importlib.import_module(
            "app.alembic.versions.20300170_0209_client_subscriptions_audit_event_id"
        )
        migration_context = MigrationContext.configure(connection)
        migration.op = Operations(migration_context)
        migration.SCHEMA = None

        migration.upgrade()
        assert "audit_event_id" in _column_names(connection, "client_subscriptions")

        migration.upgrade()
        assert "audit_event_id" in _column_names(connection, "client_subscriptions")

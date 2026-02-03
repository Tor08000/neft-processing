"""Restore clients external_id index.

Revision ID: 20299320_0160_clients_indexes_restore
Revises: 20299310_0159_clients_schema_align_with_orm
Create Date: 2026-04-18 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, create_unique_index_if_not_exists, drop_index_if_exists


revision = "20299320_0160_clients_indexes_restore"
down_revision = "20299310_0159_clients_schema_align_with_orm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_unique_index_if_not_exists(
        bind,
        "uq_clients_external_id",
        "clients",
        ["external_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(bind, "uq_clients_external_id", schema=DB_SCHEMA)

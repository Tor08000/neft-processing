"""Add client limit change requests table.

Revision ID: 20300180_0210
Revises: 20300170_0209
Create Date: 2030-01-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, drop_table_if_exists, index_exists, table_exists
from db.types import GUID


revision = "20300180_0210"
down_revision = "20300170_0209"
branch_labels = None
depends_on = None


TABLE_NAME = "client_limit_change_requests"


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        TABLE_NAME,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("limit_type", sa.String(length=128), nullable=False),
        sa.Column("new_value", sa.Numeric(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_limit_change_requests_client_id", TABLE_NAME, ["client_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_client_limit_change_requests_status", TABLE_NAME, ["status"], schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_client_limit_change_requests_status", schema=DB_SCHEMA):
        op.drop_index("ix_client_limit_change_requests_status", table_name=TABLE_NAME, schema=DB_SCHEMA)
    if index_exists(bind, "ix_client_limit_change_requests_client_id", schema=DB_SCHEMA):
        op.drop_index("ix_client_limit_change_requests_client_id", table_name=TABLE_NAME, schema=DB_SCHEMA)
    if table_exists(bind, TABLE_NAME, schema=DB_SCHEMA):
        drop_table_if_exists(bind, TABLE_NAME, schema=DB_SCHEMA)

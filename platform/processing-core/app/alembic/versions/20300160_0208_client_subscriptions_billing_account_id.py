"""Backfill billing_account_id column for client_subscriptions.

Revision ID: 20300160_0208
Revises: 20300150_0207
Create Date: 2030-01-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import SCHEMA, column_exists, table_exists


revision = "20300160_0208"
down_revision = "20300150_0207"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "client_subscriptions", schema=SCHEMA) and not column_exists(
        bind,
        "client_subscriptions",
        "billing_account_id",
        schema=SCHEMA,
    ):
        op.add_column(
            "client_subscriptions",
            sa.Column("billing_account_id", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "client_subscriptions", schema=SCHEMA) and column_exists(
        bind,
        "client_subscriptions",
        "billing_account_id",
        schema=SCHEMA,
    ):
        op.drop_column("client_subscriptions", "billing_account_id", schema=SCHEMA)

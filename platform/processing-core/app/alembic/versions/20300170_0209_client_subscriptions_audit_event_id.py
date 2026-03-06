"""Add missing audit_event_id column to client_subscriptions.

Revision ID: 20300170_0209
Revises: 20300160_0208
Create Date: 2030-01-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import SCHEMA, column_exists, table_exists


revision = "20300170_0209"
down_revision = "20300160_0208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "client_subscriptions", schema=SCHEMA) and not column_exists(
        bind,
        "client_subscriptions",
        "audit_event_id",
        schema=SCHEMA,
    ):
        op.add_column(
            "client_subscriptions",
            sa.Column("audit_event_id", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "client_subscriptions", schema=SCHEMA) and column_exists(
        bind,
        "client_subscriptions",
        "audit_event_id",
        schema=SCHEMA,
    ):
        op.drop_column("client_subscriptions", "audit_event_id", schema=SCHEMA)

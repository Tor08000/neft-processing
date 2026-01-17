"""Add suspend blocked until field for org subscriptions.

Revision ID: 20299180_0148_org_subscription_suspend_blocked_until
Revises: 20299170_0147_billing_dunning_events
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, table_exists


revision = "20299180_0148_org_subscription_suspend_blocked_until"
down_revision = "20299170_0147_billing_dunning_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "org_subscriptions", schema=DB_SCHEMA):
        return
    if column_exists(bind, "org_subscriptions", "suspend_blocked_until", schema=DB_SCHEMA):
        return
    op.add_column(
        "org_subscriptions",
        sa.Column("suspend_blocked_until", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "org_subscriptions", schema=DB_SCHEMA):
        return
    if not column_exists(bind, "org_subscriptions", "suspend_blocked_until", schema=DB_SCHEMA):
        return
    op.drop_column("org_subscriptions", "suspend_blocked_until", schema=DB_SCHEMA)

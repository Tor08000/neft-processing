"""Repair legacy notification_outbox tenant client column drift.

Revision ID: 20300230_0216_notification_outbox_tenant_client_runtime_repair
Revises: 20300220_0215_subscription_status_runtime_repair
Create Date: 2030-01-19 02:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, create_index_if_not_exists, table_exists
from db.types import GUID


revision = "20300230_0216_notification_outbox_tenant_client_runtime_repair"
down_revision = "20300220_0215_subscription_status_runtime_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "notification_outbox", schema=DB_SCHEMA):
        return

    if not column_exists(bind, "notification_outbox", "tenant_client_id", schema=DB_SCHEMA):
        op.add_column(
            "notification_outbox",
            sa.Column("tenant_client_id", GUID(), nullable=True),
            schema=DB_SCHEMA,
        )

    create_index_if_not_exists(
        bind,
        "ix_notification_outbox_tenant_client_id",
        "notification_outbox",
        ["tenant_client_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    # Keep runtime repair additive-only to avoid breaking legacy outbox consumers.
    pass

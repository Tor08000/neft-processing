"""Create transactional event outbox table.

Revision ID: 20299810_0184_event_outbox
Revises: 20299800_0183_client_portal_role_and_card_limits
Create Date: 2026-02-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID


revision = "20299810_0184_event_outbox"
down_revision = "20299800_0183_client_portal_role_and_card_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "event_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("retries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "uq_event_outbox_idempotency",
        "event_outbox",
        ["idempotency_key"],
        schema=DB_SCHEMA,
        unique=True,
    )
    create_index_if_not_exists(
        bind,
        "idx_event_outbox_pending",
        "event_outbox",
        ["status", "next_attempt_at"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_event_outbox_pending", table_name="event_outbox", schema=DB_SCHEMA)
    op.drop_index("uq_event_outbox_idempotency", table_name="event_outbox", schema=DB_SCHEMA)
    op.drop_table("event_outbox", schema=DB_SCHEMA)

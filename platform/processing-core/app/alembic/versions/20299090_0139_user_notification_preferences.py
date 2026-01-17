"""User notification preferences per user.

Revision ID: 20299090_0139_user_notification_preferences
Revises: 20299080_0138_email_outbox
Create Date: 2026-02-15 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299090_0139_user_notification_preferences"
down_revision = "20299080_0138_email_outbox"
branch_labels = None
depends_on = None


USER_NOTIFICATION_CHANNELS = ["EMAIL", "IN_APP"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "user_notification_channel", USER_NOTIFICATION_CHANNELS, schema=DB_SCHEMA)
    channel_enum = safe_enum(bind, "user_notification_channel", USER_NOTIFICATION_CHANNELS, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "user_notification_preferences",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("channel", channel_enum, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "user_id",
            "org_id",
            "event_type",
            "channel",
            name="uq_user_notification_preferences",
        ),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_user_notification_preferences_org_user",
        "user_notification_preferences",
        ["org_id", "user_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_user_notification_preferences_user_id",
        "user_notification_preferences",
        ["user_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_user_notification_preferences_org_id",
        "user_notification_preferences",
        ["org_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("user_notification_preferences", schema=DB_SCHEMA)

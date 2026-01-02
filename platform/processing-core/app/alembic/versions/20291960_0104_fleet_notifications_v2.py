"""fleet notifications v2.

Revision ID: 20291960_0104_fleet_notifications_v2
Revises: 20291950_0103_fleet_policy_actions_v1
Create Date: 2025-02-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum_value,
    safe_enum,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20291960_0104_fleet_notifications_v2"
down_revision = "20291950_0103_fleet_policy_actions_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum_value(bind, "fleet_notification_channel_type", "PUSH", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "fleet_notification_event_type", "TEST", schema=DB_SCHEMA)

    if table_exists(bind, "fleet_notification_outbox", schema=DB_SCHEMA):
        if not column_exists(bind, "fleet_notification_outbox", "delivery_message_id", schema=DB_SCHEMA):
            op.add_column("fleet_notification_outbox", sa.Column("delivery_message_id", sa.String(256), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "fleet_notification_outbox", "last_status", schema=DB_SCHEMA):
            op.add_column("fleet_notification_outbox", sa.Column("last_status", sa.String(32), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "fleet_notification_outbox", "last_response_status", schema=DB_SCHEMA):
            op.add_column("fleet_notification_outbox", sa.Column("last_response_status", sa.Integer(), nullable=True), schema=DB_SCHEMA)
        if not column_exists(bind, "fleet_notification_outbox", "last_response_body", schema=DB_SCHEMA):
            op.add_column("fleet_notification_outbox", sa.Column("last_response_body", sa.Text(), nullable=True), schema=DB_SCHEMA)

    if table_exists(bind, "fleet_push_subscriptions", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            "fleet_push_subscriptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("employee_id", sa.String(36), nullable=True),
            sa.Column("endpoint", sa.String(1024), nullable=False),
            sa.Column("p256dh", sa.String(256), nullable=False),
            sa.Column("auth", sa.String(256), nullable=False),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            "ix_fleet_push_subscriptions_client_active",
            "fleet_push_subscriptions",
            ["client_id", "active"],
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            "ix_fleet_push_subscriptions_employee",
            "fleet_push_subscriptions",
            ["employee_id"],
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass

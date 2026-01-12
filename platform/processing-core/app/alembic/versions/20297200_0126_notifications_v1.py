"""notifications v1 tables.

Revision ID: 20297200_0126_notifications_v1
Revises: 20297170_0125_legal_docs_registry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    table_exists,
)
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20297200_0126_notifications_v1"
down_revision = "20297170_0125_legal_docs_registry"
branch_labels = None
depends_on = None

NOTIFICATION_SUBJECT_TYPE = ["USER", "CLIENT", "PARTNER"]
NOTIFICATION_CHANNEL = ["EMAIL", "SMS", "TELEGRAM", "PUSH", "WEBHOOK"]
NOTIFICATION_PRIORITY = ["LOW", "NORMAL", "HIGH"]
NOTIFICATION_OUTBOX_STATUS = ["PENDING", "SENT", "FAILED", "DEAD"]
NOTIFICATION_TEMPLATE_CONTENT_TYPE = ["TEXT", "HTML", "MARKDOWN"]
NOTIFICATION_DELIVERY_STATUS = ["PENDING", "SENT", "DELIVERED", "FAILED", "RETRYING"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "notification_subject_type", NOTIFICATION_SUBJECT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "notification_channel", NOTIFICATION_CHANNEL, schema=SCHEMA)
    ensure_pg_enum(bind, "notification_priority", NOTIFICATION_PRIORITY, schema=SCHEMA)
    ensure_pg_enum(bind, "notification_outbox_status", NOTIFICATION_OUTBOX_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "notification_template_content_type", NOTIFICATION_TEMPLATE_CONTENT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "notification_delivery_status", NOTIFICATION_DELIVERY_STATUS, schema=SCHEMA)

    if not table_exists(bind, "notification_outbox", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "notification_outbox",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("event_type", sa.String(length=64), nullable=False),
                sa.Column(
                    "subject_type",
                    sa.Enum(*NOTIFICATION_SUBJECT_TYPE, name="notification_subject_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("subject_id", sa.String(length=64), nullable=False),
                sa.Column("channels", sa.JSON()),
                sa.Column("template_code", sa.String(length=128), nullable=False),
                sa.Column("template_vars", sa.JSON()),
                sa.Column(
                    "priority",
                    sa.Enum(*NOTIFICATION_PRIORITY, name="notification_priority", native_enum=False),
                    nullable=False,
                ),
                sa.Column("dedupe_key", sa.String(length=256), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*NOTIFICATION_OUTBOX_STATUS, name="notification_outbox_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
                sa.Column("last_error", sa.Text()),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_notification_outbox_dedupe",
            "notification_outbox",
            ["dedupe_key"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_notification_outbox_status",
            "notification_outbox",
            ["status", "next_attempt_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "notification_preferences", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "notification_preferences",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column(
                    "subject_type",
                    sa.Enum(*NOTIFICATION_SUBJECT_TYPE, name="notification_subject_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("subject_id", sa.String(length=64), nullable=False),
                sa.Column("event_type", sa.String(length=64), nullable=False),
                sa.Column(
                    "channel",
                    sa.Enum(*NOTIFICATION_CHANNEL, name="notification_channel", native_enum=False),
                    nullable=False,
                ),
                sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("address_override", sa.String(length=512)),
                sa.Column("quiet_hours", sa.JSON()),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_notification_prefs_subject_event",
            "notification_preferences",
            ["subject_type", "subject_id", "event_type"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "notification_templates", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "notification_templates",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("code", sa.String(length=128), nullable=False),
                sa.Column("event_type", sa.String(length=64), nullable=False),
                sa.Column(
                    "channel",
                    sa.Enum(*NOTIFICATION_CHANNEL, name="notification_channel", native_enum=False),
                    nullable=False,
                ),
                sa.Column("locale", sa.String(length=16), nullable=False, server_default="ru"),
                sa.Column("subject", sa.String(length=256)),
                sa.Column("body", sa.Text(), nullable=False),
                sa.Column(
                    "content_type",
                    sa.Enum(
                        *NOTIFICATION_TEMPLATE_CONTENT_TYPE,
                        name="notification_template_content_type",
                        native_enum=False,
                    ),
                    nullable=False,
                ),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("required_vars", sa.JSON()),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_notification_templates_code",
            "notification_templates",
            ["code"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "notification_deliveries", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "notification_deliveries",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("message_id", sa.String(length=36), nullable=False),
                sa.Column("event_type", sa.String(length=64), nullable=False),
                sa.Column(
                    "channel",
                    sa.Enum(*NOTIFICATION_CHANNEL, name="notification_channel", native_enum=False),
                    nullable=False,
                ),
                sa.Column("provider", sa.String(length=64), nullable=False),
                sa.Column("recipient", sa.String(length=256), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(*NOTIFICATION_DELIVERY_STATUS, name="notification_delivery_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("last_error", sa.Text()),
                sa.Column("provider_message_id", sa.String(length=256)),
                sa.Column("response_status", sa.Integer()),
                sa.Column("response_body", sa.Text()),
                sa.Column("sent_at", sa.DateTime(timezone=True)),
                sa.Column("delivered_at", sa.DateTime(timezone=True)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_notification_deliveries_status",
            "notification_deliveries",
            ["status"],
            schema=SCHEMA,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_notification_delivery_target",
            "notification_deliveries",
            ["message_id", "channel", "recipient"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "notification_webpush_subscriptions", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "notification_webpush_subscriptions",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column(
                    "subject_type",
                    sa.Enum(*NOTIFICATION_SUBJECT_TYPE, name="notification_subject_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("subject_id", sa.String(length=64), nullable=False),
                sa.Column("endpoint", sa.String(length=1024), nullable=False),
                sa.Column("p256dh", sa.String(length=256), nullable=False),
                sa.Column("auth", sa.String(length=256), nullable=False),
                sa.Column("user_agent", sa.String(length=512)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_notification_webpush_subject",
            "notification_webpush_subscriptions",
            ["subject_type", "subject_id"],
            schema=SCHEMA,
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_notification_webpush_endpoint",
            "notification_webpush_subscriptions",
            ["subject_type", "subject_id", "endpoint"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    # Irreversible migration (retains notification history)
    pass

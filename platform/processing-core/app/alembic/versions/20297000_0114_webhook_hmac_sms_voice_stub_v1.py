"""webhook hmac + sms/voice stub v1.

Revision ID: 20297000_0114_webhook_hmac_sms_voice_stub_v1
Revises: 20296000_0113_service_completion_proofs_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum_value,
    table_exists,
)


revision = "20297000_0114_webhook_hmac_sms_voice_stub_v1"
down_revision = "20296000_0113_service_completion_proofs_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum_value(bind, "fleet_notification_channel_type", "SMS", schema=DB_SCHEMA)
    ensure_pg_enum_value(bind, "fleet_notification_channel_type", "VOICE", schema=DB_SCHEMA)

    if table_exists(bind, "webhook_endpoints", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "webhook_endpoints",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("owner_type", sa.String(32), nullable=False),
            sa.Column("owner_id", sa.String(36), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("secret", sa.Text(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("allowed_events", sa.JSON(), nullable=True),
            sa.Column("retry_policy", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_webhook_endpoints_owner",
            "webhook_endpoints",
            ["owner_id", "owner_type"],
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "webhook_delivery_attempts", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "webhook_delivery_attempts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event_id", sa.String(36), nullable=False),
            sa.Column("endpoint_id", sa.String(36), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("response_body_snippet", sa.Text(), nullable=True),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dedupe_key", sa.String(256), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_webhook_delivery_attempts_endpoint_event",
            "webhook_delivery_attempts",
            ["endpoint_id", "event_id"],
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_webhook_delivery_attempts_dedupe",
            "webhook_delivery_attempts",
            ["dedupe_key"],
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "webhook_nonce_store", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "webhook_nonce_store",
            sa.Column("nonce", sa.String(64), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_webhook_nonce_store_expires",
            "webhook_nonce_store",
            ["expires_at"],
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "notification_delivery_logs", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "notification_delivery_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=True),
            sa.Column("channel", sa.String(32), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("message_id", sa.String(128), nullable=False),
            sa.Column("recipient", sa.String(256), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("payload_hash", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_notification_delivery_logs_channel_status",
            "notification_delivery_logs",
            ["channel", "status"],
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    # No downgrade operations for additive changes.
    pass

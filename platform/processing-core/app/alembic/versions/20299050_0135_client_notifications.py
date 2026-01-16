"""Client portal notifications.

Revision ID: 20299050_0135_client_notifications
Revises: 20299040_0134_support_ticket_attachments
Create Date: 2026-02-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299050_0135_client_notifications"
down_revision = "20299040_0134_support_ticket_attachments"
branch_labels = None
depends_on = None


NOTIFICATION_SEVERITY = ["INFO", "WARNING", "CRITICAL"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "client_notification_severity", NOTIFICATION_SEVERITY, schema=DB_SCHEMA)
    severity_enum = safe_enum(bind, "client_notification_severity", NOTIFICATION_SEVERITY, schema=DB_SCHEMA)
    roles_array = postgresql.ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")
    json_type = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")

    create_table_if_not_exists(
        bind,
        "client_notifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("target_user_id", sa.String(128), nullable=True),
        sa.Column("target_roles", roles_array, nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", severity_enum, nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(255), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_email_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_json", json_type, nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_client_notifications_org_id", "client_notifications", ["org_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_client_notifications_target_user_id",
        "client_notifications",
        ["target_user_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_notifications_org_read",
        "client_notifications",
        ["org_id", "read_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_notifications_org_created",
        "client_notifications",
        ["org_id", "created_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_notifications_type",
        "client_notifications",
        ["type"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("client_notifications", schema=DB_SCHEMA)

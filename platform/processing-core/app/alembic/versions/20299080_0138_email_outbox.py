"""Email outbox for production delivery.

Revision ID: 20299080_0138_email_outbox
Revises: 20299070_0137_report_schedules
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299080_0138_email_outbox"
down_revision = "20299070_0137_report_schedules"
branch_labels = None
depends_on = None


EMAIL_OUTBOX_STATUS = ["QUEUED", "SENT", "FAILED"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "email_outbox_status", EMAIL_OUTBOX_STATUS, schema=DB_SCHEMA)
    status_enum = safe_enum(bind, "email_outbox_status", EMAIL_OUTBOX_STATUS, schema=DB_SCHEMA)
    json_type = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")

    create_table_if_not_exists(
        bind,
        "email_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False, unique=True),
        sa.Column("to_emails", json_type, nullable=False),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("tags", json_type, nullable=True),
        sa.Column("template_key", sa.String(128), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="QUEUED"),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("provider_message_id", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_email_outbox_status_retry",
        "email_outbox",
        ["status", "next_retry_at"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_email_outbox_idempotency",
        "email_outbox",
        ["idempotency_key"],
        schema=DB_SCHEMA,
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("email_outbox", schema=DB_SCHEMA)

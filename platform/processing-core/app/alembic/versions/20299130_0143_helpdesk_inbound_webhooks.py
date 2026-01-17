"""Helpdesk inbound webhook events.

Revision ID: 20299130_0143_helpdesk_inbound_webhooks
Revises: 20299120_0142_helpdesk_integrations
Create Date: 2026-03-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID

revision = "20299130_0143_helpdesk_inbound_webhooks"
down_revision = "20299120_0142_helpdesk_integrations"
branch_labels = None
depends_on = None

HELPDESK_INBOUND_EVENT_STATUS = ["PROCESSED", "IGNORED", "FAILED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "helpdesk_inbound_event_status", HELPDESK_INBOUND_EVENT_STATUS, schema=DB_SCHEMA)
    inbound_status_enum = safe_enum(bind, "helpdesk_inbound_event_status", HELPDESK_INBOUND_EVENT_STATUS, schema=DB_SCHEMA)
    provider_enum = safe_enum(bind, "helpdesk_provider", ["zendesk", "jira_sm"], schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "helpdesk_inbound_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", inbound_status_enum, nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "event_id", name="uq_helpdesk_inbound_events_scope"),
        schema=DB_SCHEMA,
    )

    op.add_column("support_tickets", sa.Column("last_changed_by", sa.String(length=128), nullable=True), schema=DB_SCHEMA)
    op.add_column(
        "support_ticket_comments",
        sa.Column("source", sa.String(length=64), nullable=True),
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("support_ticket_comments", "source", schema=DB_SCHEMA)
    op.drop_column("support_tickets", "last_changed_by", schema=DB_SCHEMA)
    op.drop_table("helpdesk_inbound_events", schema=DB_SCHEMA)

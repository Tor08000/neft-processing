"""Helpdesk integrations and outbox tables.

Revision ID: 20299120_0142_helpdesk_integrations
Revises: 20299110_0141_client_employee_timezone
Create Date: 2026-02-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import (
    DB_SCHEMA,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    safe_enum,
)
from db.types import GUID

revision = "20299120_0142_helpdesk_integrations"
down_revision = "20299110_0141_client_employee_timezone"
branch_labels = None
depends_on = None

HELPDESK_PROVIDER = ["zendesk", "jira_sm"]
HELPDESK_INTEGRATION_STATUS = ["ACTIVE", "DISABLED"]
HELPDESK_TICKET_LINK_STATUS = ["LINKED", "FAILED"]
HELPDESK_OUTBOX_STATUS = ["QUEUED", "SENT", "FAILED"]
HELPDESK_OUTBOX_EVENT_TYPE = ["TICKET_CREATED", "COMMENT_ADDED", "TICKET_CLOSED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "helpdesk_provider", HELPDESK_PROVIDER, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "helpdesk_integration_status", HELPDESK_INTEGRATION_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "helpdesk_ticket_link_status", HELPDESK_TICKET_LINK_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "helpdesk_outbox_status", HELPDESK_OUTBOX_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "helpdesk_outbox_event_type", HELPDESK_OUTBOX_EVENT_TYPE, schema=DB_SCHEMA)

    provider_enum = safe_enum(bind, "helpdesk_provider", HELPDESK_PROVIDER, schema=DB_SCHEMA)
    integration_status_enum = safe_enum(bind, "helpdesk_integration_status", HELPDESK_INTEGRATION_STATUS, schema=DB_SCHEMA)
    link_status_enum = safe_enum(bind, "helpdesk_ticket_link_status", HELPDESK_TICKET_LINK_STATUS, schema=DB_SCHEMA)
    outbox_status_enum = safe_enum(bind, "helpdesk_outbox_status", HELPDESK_OUTBOX_STATUS, schema=DB_SCHEMA)
    outbox_event_enum = safe_enum(bind, "helpdesk_outbox_event_type", HELPDESK_OUTBOX_EVENT_TYPE, schema=DB_SCHEMA)

    json_type = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")

    create_table_if_not_exists(
        bind,
        "helpdesk_integrations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("status", integration_status_enum, nullable=False),
        sa.Column("config_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "provider", name="uq_helpdesk_integrations_scope"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_helpdesk_integrations_org",
        "helpdesk_integrations",
        ["org_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "helpdesk_ticket_links",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("internal_ticket_id", GUID(), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("external_ticket_id", sa.String(128), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("status", link_status_enum, nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "internal_ticket_id", name="uq_helpdesk_ticket_links_scope"),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_helpdesk_ticket_links_org",
        "helpdesk_ticket_links",
        ["org_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_helpdesk_ticket_links_ticket",
        "helpdesk_ticket_links",
        ["internal_ticket_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "helpdesk_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("internal_ticket_id", GUID(), nullable=False),
        sa.Column("event_type", outbox_event_enum, nullable=False),
        sa.Column("payload_json", json_type, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("status", outbox_status_enum, nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_helpdesk_outbox_org", "helpdesk_outbox", ["org_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_helpdesk_outbox_status",
        "helpdesk_outbox",
        ["status"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_helpdesk_outbox_retry",
        "helpdesk_outbox",
        ["next_retry_at"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("helpdesk_outbox", schema=DB_SCHEMA)
    op.drop_table("helpdesk_ticket_links", schema=DB_SCHEMA)
    op.drop_table("helpdesk_integrations", schema=DB_SCHEMA)

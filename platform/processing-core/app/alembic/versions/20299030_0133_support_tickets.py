"""Support tickets for client portal.

Revision ID: 20299030_0133_support_tickets
Revises: 20299020_0132_limit_templates
Create Date: 2026-01-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299030_0133_support_tickets"
down_revision = "20299020_0132_limit_templates"
branch_labels = None
depends_on = None


SUPPORT_TICKET_STATUS = ["OPEN", "IN_PROGRESS", "CLOSED"]
SUPPORT_TICKET_PRIORITY = ["LOW", "NORMAL", "HIGH"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "support_ticket_status", SUPPORT_TICKET_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "support_ticket_priority", SUPPORT_TICKET_PRIORITY, schema=DB_SCHEMA)
    status_enum = safe_enum(bind, "support_ticket_status", SUPPORT_TICKET_STATUS, schema=DB_SCHEMA)
    priority_enum = safe_enum(bind, "support_ticket_priority", SUPPORT_TICKET_PRIORITY, schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "support_tickets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("created_by_user_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="OPEN"),
        sa.Column("priority", priority_enum, nullable=False, server_default="NORMAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_support_tickets_org_id", "support_tickets", ["org_id"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind, "ix_support_tickets_created_by_user_id", "support_tickets", ["created_by_user_id"], schema=DB_SCHEMA
    )
    create_index_if_not_exists(bind, "ix_support_tickets_status", "support_tickets", ["status"], schema=DB_SCHEMA)
    create_index_if_not_exists(bind, "ix_support_tickets_priority", "support_tickets", ["priority"], schema=DB_SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_support_tickets_org_creator",
        "support_tickets",
        ["org_id", "created_by_user_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "support_ticket_comments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "ticket_id",
            GUID(),
            sa.ForeignKey(f"{DB_SCHEMA}.support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind, "ix_support_ticket_comments_ticket_id", "support_ticket_comments", ["ticket_id"], schema=DB_SCHEMA
    )


def downgrade() -> None:
    op.drop_table("support_ticket_comments", schema=DB_SCHEMA)
    op.drop_table("support_tickets", schema=DB_SCHEMA)

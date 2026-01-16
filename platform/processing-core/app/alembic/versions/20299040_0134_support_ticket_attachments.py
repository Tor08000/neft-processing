"""Support ticket attachments.

Revision ID: 20299040_0134_support_ticket_attachments
Revises: 20299030_0133_support_tickets
Create Date: 2026-02-05 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID


revision = "20299040_0134_support_ticket_attachments"
down_revision = "20299030_0133_support_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "support_ticket_attachments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "ticket_id",
            GUID(),
            sa.ForeignKey(f"{DB_SCHEMA}.support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", GUID(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(128), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_support_ticket_attachments_ticket_id",
        "support_ticket_attachments",
        ["ticket_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_support_ticket_attachments_org_id",
        "support_ticket_attachments",
        ["org_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("support_ticket_attachments", schema=DB_SCHEMA)

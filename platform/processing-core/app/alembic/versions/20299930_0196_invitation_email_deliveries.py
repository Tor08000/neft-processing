"""Add invitation email deliveries and used_at for one-time links.

Revision ID: 20299930_0196_invitation_email_deliveries
Revises: 20299920_0195_client_invitation_indexes
Create Date: 2026-02-19 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID

revision = "20299930_0196_invitation_email_deliveries"
down_revision = "20299920_0195_client_invitation_indexes"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table, schema=DB_SCHEMA))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("client_invitations", schema=DB_SCHEMA) and not _has_column(inspector, "client_invitations", "used_at"):
        op.add_column("client_invitations", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)

    create_table_if_not_exists(
        bind,
        "invitation_email_deliveries",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("invitation_id", GUID(), sa.ForeignKey("client_invitations.id"), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="EMAIL"),
        sa.Column("provider", sa.Text(), nullable=False, server_default="integration-hub"),
        sa.Column("to_email", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="QUEUED"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invitation_email_deliveries_invitation_id",
        "invitation_email_deliveries",
        ["invitation_id"],
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_invitation_email_deliveries_status",
        "invitation_email_deliveries",
        ["status"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_invitation_email_deliveries_status", table_name="invitation_email_deliveries", schema=DB_SCHEMA)
    op.drop_index("ix_invitation_email_deliveries_invitation_id", table_name="invitation_email_deliveries", schema=DB_SCHEMA)
    op.drop_table("invitation_email_deliveries", schema=DB_SCHEMA)
    op.drop_column("client_invitations", "used_at", schema=DB_SCHEMA)

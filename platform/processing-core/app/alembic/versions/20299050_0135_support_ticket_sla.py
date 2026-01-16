"""Support ticket SLA fields.

Revision ID: 20299050_0135_support_ticket_sla
Revises: 20299040_0134_support_ticket_attachments
Create Date: 2026-02-12 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.types import GUID


revision = "20299050_0135_support_ticket_sla"
down_revision = "20299040_0134_support_ticket_attachments"
branch_labels = None
depends_on = None


SUPPORT_TICKET_SLA_STATUS = ["OK", "BREACHED", "PENDING"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "support_ticket_sla_status", SUPPORT_TICKET_SLA_STATUS, schema=DB_SCHEMA)
    sla_status_enum = safe_enum(bind, "support_ticket_sla_status", SUPPORT_TICKET_SLA_STATUS, schema=DB_SCHEMA)

    if not column_exists(bind, "support_tickets", "first_response_due_at", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "support_tickets", "first_response_at", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "support_tickets", "resolution_due_at", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "support_tickets", "resolved_at", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "support_tickets", "sla_first_response_status", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column(
                "sla_first_response_status",
                sla_status_enum,
                nullable=False,
                server_default="PENDING",
            ),
            schema=DB_SCHEMA,
        )
    if not column_exists(bind, "support_tickets", "sla_resolution_status", schema=DB_SCHEMA):
        op.add_column(
            "support_tickets",
            sa.Column(
                "sla_resolution_status",
                sla_status_enum,
                nullable=False,
                server_default="PENDING",
            ),
            schema=DB_SCHEMA,
        )

    create_table_if_not_exists(
        bind,
        "support_ticket_sla_policies",
        sa.Column("org_id", GUID(), primary_key=True),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()

    if column_exists(bind, "support_tickets", "sla_resolution_status", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "sla_resolution_status", schema=DB_SCHEMA)
    if column_exists(bind, "support_tickets", "sla_first_response_status", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "sla_first_response_status", schema=DB_SCHEMA)
    if column_exists(bind, "support_tickets", "resolved_at", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "resolved_at", schema=DB_SCHEMA)
    if column_exists(bind, "support_tickets", "resolution_due_at", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "resolution_due_at", schema=DB_SCHEMA)
    if column_exists(bind, "support_tickets", "first_response_at", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "first_response_at", schema=DB_SCHEMA)
    if column_exists(bind, "support_tickets", "first_response_due_at", schema=DB_SCHEMA):
        op.drop_column("support_tickets", "first_response_due_at", schema=DB_SCHEMA)

    op.drop_table("support_ticket_sla_policies", schema=DB_SCHEMA)

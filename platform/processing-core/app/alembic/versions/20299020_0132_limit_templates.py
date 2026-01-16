"""Limit templates for client portal.

Revision ID: 20299020_0132_limit_templates
Revises: 20299010_0131_client_onboarding_mvp
Create Date: 2026-01-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID


revision = "20299020_0132_limit_templates"
down_revision = "20299010_0131_client_onboarding_mvp"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "limit_templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("limits", JSON_TYPE, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_limit_templates_client_id",
        "limit_templates",
        ["client_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("limit_templates", schema=DB_SCHEMA)

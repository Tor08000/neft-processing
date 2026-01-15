"""Client onboarding MVP tables.

Revision ID: 20299010_0131_client_onboarding_mvp
Revises: 20299000_0130_merge_heads_processing_core
Create Date: 2026-01-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from alembic_helpers import DB_SCHEMA, create_index_if_not_exists, create_table_if_not_exists
from db.types import GUID


revision = "20299010_0131_client_onboarding_mvp"
down_revision = "20299000_0130_merge_heads_processing_core"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "feature_flags",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("on", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("segment", sa.String(128), nullable=True),
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "client_onboarding_contracts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("client_id", GUID(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signature_meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_onboarding_contracts_client_id",
        "client_onboarding_contracts",
        ["client_id"],
        schema=DB_SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "client_onboarding",
        sa.Column("client_id", GUID(), primary_key=True),
        sa.Column("owner_user_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(32), nullable=False, server_default="PROFILE"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("client_type", sa.String(32), nullable=True),
        sa.Column("profile_json", JSON_TYPE, nullable=True),
        sa.Column("contract_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=DB_SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_client_onboarding_owner_user_id",
        "client_onboarding",
        ["owner_user_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("client_onboarding", schema=DB_SCHEMA)
    op.drop_table("client_onboarding_contracts", schema=DB_SCHEMA)
    op.drop_table("feature_flags", schema=DB_SCHEMA)

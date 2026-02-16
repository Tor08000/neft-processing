"""Client onboarding applications.

Revision ID: 20299830_0186_client_onboarding_applications
Revises: 20299820_0185_partner_management_v1
Create Date: 2026-02-16 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

from alembic_helpers import DB_SCHEMA
from db.types import GUID

revision = "20299830_0186_client_onboarding_applications"
down_revision = "20299820_0185_partner_management_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_onboarding_applications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("inn", sa.Text(), nullable=True),
        sa.Column("ogrn", sa.Text(), nullable=True),
        sa.Column("org_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        schema=DB_SCHEMA,
    )

    op.create_index(
        "ix_client_onboarding_applications_lower_email",
        "client_onboarding_applications",
        [sa.text("lower(email)")],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "ix_client_onboarding_applications_status",
        "client_onboarding_applications",
        ["status"],
        schema=DB_SCHEMA,
    )
    op.create_index(
        "ix_client_onboarding_applications_created_by_user_id",
        "client_onboarding_applications",
        ["created_by_user_id"],
        schema=DB_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_client_onboarding_applications_created_by_user_id", table_name="client_onboarding_applications", schema=DB_SCHEMA)
    op.drop_index("ix_client_onboarding_applications_status", table_name="client_onboarding_applications", schema=DB_SCHEMA)
    op.drop_index("ix_client_onboarding_applications_lower_email", table_name="client_onboarding_applications", schema=DB_SCHEMA)
    op.drop_table("client_onboarding_applications", schema=DB_SCHEMA)

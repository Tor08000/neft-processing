"""Add correlation_id to partner payout requests.

Revision ID: 20299290_0157_partner_payout_correlation_id
Revises: 20299280_0156_merge_heads_billing_notifications_exports
Create Date: 2026-04-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20299290_0157_partner_payout_correlation_id"
down_revision = "20299280_0156_merge_heads_billing_notifications_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("partner_payout_requests", sa.Column("correlation_id", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_partner_payout_correlation_id",
        "partner_payout_requests",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_payout_correlation_id", table_name="partner_payout_requests")
    op.drop_column("partner_payout_requests", "correlation_id")

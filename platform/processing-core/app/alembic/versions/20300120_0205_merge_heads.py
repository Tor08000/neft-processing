"""Merge heads 0195/0196/0203/0204 into a single head.

Revision ID: 20300120_0205_merge_heads
Revises: 20299920_0195_client_cards_limits_v1, 20299930_0196_invitation_email_deliveries, 20300030_0203_otp_challenges_doc_sign, 20300110_0204_client_docflow_package_notifications_upgrade
Create Date: 2026-02-17 00:00:00.000000
"""

from __future__ import annotations


revision = "20300120_0205_merge_heads"
down_revision = (
    "20299920_0195_client_cards_limits_v1",
    "20299930_0196_invitation_email_deliveries",
    "20300030_0203_otp_challenges_doc_sign",
    "20300110_0204_client_docflow_package_notifications_upgrade",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

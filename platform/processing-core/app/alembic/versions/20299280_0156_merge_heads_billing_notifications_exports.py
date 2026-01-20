"""Merge heads for billing payment intakes, client notifications, export job format, and partner trust exports.

Revision ID: 20299280_0156_merge_heads_billing_notifications_exports
Revises: 20297305_0129_billing_payment_intakes, 20299050_0135_client_notifications, 20299070_0137_export_job_format_xlsx, 20299270_0155_partner_trust_exports
Create Date: 2026-04-11 00:00:00.000000
"""

from __future__ import annotations

revision = "20299280_0156_merge_heads_billing_notifications_exports"
down_revision = (
    "20297305_0129_billing_payment_intakes",
    "20299050_0135_client_notifications",
    "20299070_0137_export_job_format_xlsx",
    "20299270_0155_partner_trust_exports",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply merge revision."""
    pass


def downgrade() -> None:
    """Rollback merge revision."""
    pass

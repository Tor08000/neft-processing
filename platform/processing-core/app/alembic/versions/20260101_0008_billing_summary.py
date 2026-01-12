"""create billing_summary table

Revision ID: 20260101_0008_billing_summary
Revises: 20251230_0007_add_capture_refund_fields_to_operations
Create Date: 2026-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
)

# revision identifiers, used by Alembic.
revision = "20260101_0008_billing_summary"
down_revision = "20251230_0007_add_capture_refund_fields_to_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_not_exists(
        bind,
        "billing_summary",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("total_captured_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("date", "merchant_id", name="uq_billing_summary_date_merchant"),
    )
    create_index_if_not_exists(bind, "ix_billing_summary_date", "billing_summary", ["date"])
    create_index_if_not_exists(
        bind, "ix_billing_summary_merchant_id", "billing_summary", ["merchant_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(bind, "ix_billing_summary_merchant_id")
    drop_index_if_exists(bind, "ix_billing_summary_date")
    drop_table_if_exists(bind, "billing_summary")

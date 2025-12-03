"""extend billing_summary with status and hash

Revision ID: 20260110_0009_billing_summary_extend
Revises: 20260101_0008_billing_summary
Create Date: 2025-06-10
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260110_0009_billing_summary_extend"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


STATUS_ENUM = sa.Enum("PENDING", "FINALIZED", name="billing_summary_status")


def upgrade() -> None:
    op.add_column(
        "billing_summary",
        sa.Column(
            "status",
            STATUS_ENUM,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "billing_summary",
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "billing_summary",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "billing_summary",
        sa.Column("hash", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_billing_summary_status", "billing_summary", ["status"], unique=False
    )
    op.create_index(
        "ix_billing_summary_generated_at",
        "billing_summary",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_billing_summary_generated_at", table_name="billing_summary")
    op.drop_index("ix_billing_summary_status", table_name="billing_summary")
    op.drop_column("billing_summary", "hash")
    op.drop_column("billing_summary", "finalized_at")
    op.drop_column("billing_summary", "generated_at")
    op.drop_column("billing_summary", "status")
    STATUS_ENUM.drop(op.get_bind())

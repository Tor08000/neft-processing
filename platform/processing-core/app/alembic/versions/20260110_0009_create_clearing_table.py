"""create clearing table

Revision ID: 20260110_0009_create_clearing_table
Revises: 20260101_0008_billing_summary
Create Date: 2026-01-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260110_0009_create_clearing_table"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clearing",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_date", sa.Date(), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", name="clearing_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "batch_date",
            "merchant_id",
            "currency",
            name="uq_clearing_date_merchant_currency",
        ),
    )
    op.create_index("ix_clearing_batch_date", "clearing", ["batch_date"])
    op.create_index("ix_clearing_merchant_id", "clearing", ["merchant_id"])
    op.create_index("ix_clearing_currency", "clearing", ["currency"])
    op.create_index("ix_clearing_status", "clearing", ["status"])


def downgrade() -> None:
    op.drop_index("ix_clearing_status", table_name="clearing")
    op.drop_index("ix_clearing_currency", table_name="clearing")
    op.drop_index("ix_clearing_merchant_id", table_name="clearing")
    op.drop_index("ix_clearing_batch_date", table_name="clearing")
    op.drop_table("clearing")
    op.execute("DROP TYPE IF EXISTS clearing_status")

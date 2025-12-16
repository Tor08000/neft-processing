"""create clearing table

Revision ID: 20260110_0009_create_clearing_table
Revises: 20260101_0008_billing_summary
Create Date: 2026-01-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    drop_index_if_exists,
    ensure_enum_type_exists,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20260110_0009_create_clearing_table"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    clearing_status = postgresql.ENUM("PENDING", name="clearing_status", create_type=False)
    ensure_enum_type_exists(bind, type_name=clearing_status.name, values=list(clearing_status.enums))

    if not table_exists(bind, "clearing"):
        op.create_table(
            "clearing",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("batch_date", sa.Date(), nullable=False),
            sa.Column("merchant_id", sa.String(length=64), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("total_amount", sa.BigInteger(), nullable=False),
            sa.Column(
                "status",
                clearing_status,
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
    create_index_if_not_exists(bind, "ix_clearing_batch_date", "clearing", ["batch_date"])
    create_index_if_not_exists(bind, "ix_clearing_merchant_id", "clearing", ["merchant_id"])
    create_index_if_not_exists(bind, "ix_clearing_currency", "clearing", ["currency"])
    create_index_if_not_exists(bind, "ix_clearing_status", "clearing", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(bind, "ix_clearing_status", table_name="clearing")
    drop_index_if_exists(bind, "ix_clearing_currency", table_name="clearing")
    drop_index_if_exists(bind, "ix_clearing_merchant_id", table_name="clearing")
    drop_index_if_exists(bind, "ix_clearing_batch_date", table_name="clearing")
    if table_exists(bind, "clearing"):
        op.drop_table("clearing")
    bind.exec_driver_sql("DROP TYPE IF EXISTS clearing_status")

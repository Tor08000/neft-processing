"""create clearing tables

Revision ID: 20260110_0010_clearing
Revises: 20260110_0009_billing_summary_extend
Create Date: 2025-06-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
)

# revision identifiers, used by Alembic.
revision = "20260110_0010_clearing"
down_revision = "20260110_0009_billing_summary_extend"
branch_labels = None
depends_on = None


BATCH_STATUS_VALUES = ["PENDING", "SENT", "CONFIRMED", "FAILED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "clearing_batch_status", values=BATCH_STATUS_VALUES)
    batch_status = safe_enum(
        bind, "clearing_batch_status", values=BATCH_STATUS_VALUES, schema="public"
    )

    create_table_if_not_exists(
        bind,
        "clearing_batch",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("merchant_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("date_from", sa.Date(), nullable=False, index=True),
        sa.Column("date_to", sa.Date(), nullable=False, index=True),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            batch_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    create_index_if_not_exists(bind, "ix_clearing_batch_status", "clearing_batch", ["status"])
    create_index_if_not_exists(
        bind, "ix_clearing_batch_merchant_id", "clearing_batch", ["merchant_id"]
    )
    create_index_if_not_exists(
        bind, "ix_clearing_batch_date_from", "clearing_batch", ["date_from"]
    )
    create_index_if_not_exists(bind, "ix_clearing_batch_date_to", "clearing_batch", ["date_to"])

    create_table_if_not_exists(
        bind,
        "clearing_batch_operation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(length=36), sa.ForeignKey("clearing_batch.id"), nullable=False
        ),
        sa.Column(
            "operation_id",
            sa.String(length=64),
            sa.ForeignKey("operations.operation_id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
    )

    create_index_if_not_exists(
        bind,
        "ix_clearing_batch_operation_batch_id",
        "clearing_batch_operation",
        ["batch_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(
        bind, "ix_clearing_batch_operation_batch_id", table_name="clearing_batch_operation"
    )
    drop_table_if_exists(bind, "clearing_batch_operation")
    drop_index_if_exists(bind, "ix_clearing_batch_date_to", table_name="clearing_batch")
    drop_index_if_exists(bind, "ix_clearing_batch_date_from", table_name="clearing_batch")
    drop_index_if_exists(bind, "ix_clearing_batch_merchant_id", table_name="clearing_batch")
    drop_index_if_exists(bind, "ix_clearing_batch_status", table_name="clearing_batch")
    drop_table_if_exists(bind, "clearing_batch")
    postgresql.ENUM(name="clearing_batch_status", create_type=False).drop(
        bind, checkfirst=True
    )

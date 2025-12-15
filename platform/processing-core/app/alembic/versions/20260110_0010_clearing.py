"""create clearing tables

Revision ID: 20260110_0010_clearing
Revises: 20260110_0009_billing_summary_extend
Create Date: 2025-06-10
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260110_0010_clearing"
down_revision = "20260110_0009_billing_summary_extend"
branch_labels = None
depends_on = None


BATCH_STATUS = sa.Enum(
    "PENDING", "SENT", "CONFIRMED", "FAILED", name="clearing_batch_status"
)


def _table_exists(bind, table_name: str) -> bool:
    qname = table_name if "." in table_name else f"public.{table_name}"
    return bool(bind.exec_driver_sql("SELECT to_regclass(%s)", (qname,)).scalar())


def _create_index_if_not_exists(index_name: str, table_name: str, *columns: str) -> None:
    columns_sql = ", ".join(columns)
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "clearing_batch"):
        op.create_table(
            "clearing_batch",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("merchant_id", sa.String(length=64), nullable=False, index=True),
            sa.Column("date_from", sa.Date(), nullable=False, index=True),
            sa.Column("date_to", sa.Date(), nullable=False, index=True),
            sa.Column("total_amount", sa.Integer(), nullable=False),
            sa.Column("operations_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "status",
                BATCH_STATUS,
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

    _create_index_if_not_exists("ix_clearing_batch_status", "clearing_batch", "status")
    _create_index_if_not_exists(
        "ix_clearing_batch_merchant_id", "clearing_batch", "merchant_id"
    )
    _create_index_if_not_exists(
        "ix_clearing_batch_date_from", "clearing_batch", "date_from"
    )
    _create_index_if_not_exists("ix_clearing_batch_date_to", "clearing_batch", "date_to")

    if not _table_exists(bind, "clearing_batch_operation"):
        op.create_table(
            "clearing_batch_operation",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("clearing_batch.id"), nullable=False),
            sa.Column(
                "operation_id",
                sa.String(length=64),
                sa.ForeignKey("operations.operation_id"),
                nullable=False,
            ),
            sa.Column("amount", sa.Integer(), nullable=False),
        )

    _create_index_if_not_exists(
        "ix_clearing_batch_operation_batch_id",
        "clearing_batch_operation",
        "batch_id",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clearing_batch_operation_batch_id", table_name="clearing_batch_operation"
    )
    op.drop_table("clearing_batch_operation")
    op.drop_index("ix_clearing_batch_date_to", table_name="clearing_batch")
    op.drop_index("ix_clearing_batch_date_from", table_name="clearing_batch")
    op.drop_index("ix_clearing_batch_merchant_id", table_name="clearing_batch")
    op.drop_index("ix_clearing_batch_status", table_name="clearing_batch")
    op.drop_table("clearing_batch")
    BATCH_STATUS.drop(op.get_bind())

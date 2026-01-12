"""extend billing_summary with status and hash

Revision ID: 20260110_0009_billing_summary_extend
Revises: 20260101_0008_billing_summary
Create Date: 2025-06-10
"""

from alembic import op
import sqlalchemy as sa

from alembic_helpers import (
    create_index_if_not_exists,
    drop_index_if_exists,
    ensure_pg_enum,
    safe_enum,
)


# revision identifiers, used by Alembic.
revision = "20260110_0009_billing_summary_extend"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


def _ensure_status_enum_exists(connection):
    ensure_pg_enum(connection, "billing_summary_status", values=["PENDING", "FINALIZED"])


def _table_state(inspector):
    return {
        "columns": {col["name"] for col in inspector.get_columns("billing_summary")},
        "indexes": {ix["name"] for ix in inspector.get_indexes("billing_summary")},
    }


def upgrade() -> None:
    bind = op.get_bind()
    setattr(bind, "op_override", op)
    _ensure_status_enum_exists(bind)
    status_enum = safe_enum(bind, "billing_summary_status", values=["PENDING", "FINALIZED"])

    inspector = sa.inspect(bind)
    state = _table_state(inspector)

    if "status" not in state["columns"]:
        op.add_column(
            "billing_summary",
            sa.Column(
                "status",
                status_enum,
                nullable=False,
                server_default="PENDING",
            ),
        )
    if "generated_at" not in state["columns"]:
        op.add_column(
            "billing_summary",
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if "finalized_at" not in state["columns"]:
        op.add_column(
            "billing_summary",
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "hash" not in state["columns"]:
        op.add_column(
            "billing_summary",
            sa.Column("hash", sa.String(length=128), nullable=True),
        )

    create_index_if_not_exists(bind, "ix_billing_summary_status", "billing_summary", ["status"], unique=False)
    create_index_if_not_exists(
        bind,
        "ix_billing_summary_generated_at",
        "billing_summary",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    state = _table_state(inspector)

    drop_index_if_exists(bind, "ix_billing_summary_generated_at")
    drop_index_if_exists(bind, "ix_billing_summary_status")

    if "hash" in state["columns"]:
        op.drop_column("billing_summary", "hash")
    if "finalized_at" in state["columns"]:
        op.drop_column("billing_summary", "finalized_at")
    if "generated_at" in state["columns"]:
        op.drop_column("billing_summary", "generated_at")
    if "status" in state["columns"]:
        op.drop_column("billing_summary", "status")

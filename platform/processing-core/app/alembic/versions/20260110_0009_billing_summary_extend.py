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


STATUS_ENUM = sa.Enum(
    "PENDING",
    "FINALIZED",
    name="billing_summary_status",
    create_type=False,  # тип создаём явно через DO $$ чтобы повторный прогон не падал
)


def _ensure_status_enum_exists(connection):
    connection.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'billing_summary_status'
            ) THEN
                CREATE TYPE billing_summary_status AS ENUM (
                    'PENDING',
                    'FINALIZED'
                );
            END IF;
        END $$;
        """
    )


def _table_state(inspector):
    return {
        "columns": {col["name"] for col in inspector.get_columns("billing_summary")},
        "indexes": {ix["name"] for ix in inspector.get_indexes("billing_summary")},
    }


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_status_enum_exists(bind)

    inspector = sa.inspect(bind)
    state = _table_state(inspector)

    if "status" not in state["columns"]:
        op.add_column(
            "billing_summary",
            sa.Column(
                "status",
                STATUS_ENUM,
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

    if "ix_billing_summary_status" not in state["indexes"]:
        op.create_index(
            "ix_billing_summary_status", "billing_summary", ["status"], unique=False
        )
    if "ix_billing_summary_generated_at" not in state["indexes"]:
        op.create_index(
            "ix_billing_summary_generated_at",
            "billing_summary",
            ["generated_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    state = _table_state(inspector)

    if "ix_billing_summary_generated_at" in state["indexes"]:
        op.drop_index("ix_billing_summary_generated_at", table_name="billing_summary")
    if "ix_billing_summary_status" in state["indexes"]:
        op.drop_index("ix_billing_summary_status", table_name="billing_summary")

    if "hash" in state["columns"]:
        op.drop_column("billing_summary", "hash")
    if "finalized_at" in state["columns"]:
        op.drop_column("billing_summary", "finalized_at")
    if "generated_at" in state["columns"]:
        op.drop_column("billing_summary", "generated_at")
    if "status" in state["columns"]:
        op.drop_column("billing_summary", "status")

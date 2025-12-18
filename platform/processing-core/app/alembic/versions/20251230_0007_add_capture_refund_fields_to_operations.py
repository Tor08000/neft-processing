"""add capture/refund aggregates to operations

Revision ID: 20251230_0007_add_capture_refund_fields_to_operations
Revises: 20251220_0006_auto_fix
Create Date: 2025-12-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251230_0007_add_capture_refund_fields_to_operations"
down_revision = "20251220_0006_auto_fix"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str, schema: str = "public") -> bool:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            select 1
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :col
            limit 1
            """
        ),
        {"schema": schema, "table": table, "col": column},
    ).fetchone()

    return row is not None


def upgrade():
    schema = "public"

    if not _column_exists("operations", "captured_amount", schema):
        op.add_column(
            "operations",
            sa.Column("captured_amount", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )

    if not _column_exists("operations", "refunded_amount", schema):
        op.add_column(
            "operations",
            sa.Column("refunded_amount", sa.BigInteger(), nullable=False, server_default="0"),
            schema=schema,
        )

    op.execute("UPDATE operations SET captured_amount = 0 WHERE captured_amount IS NULL")
    op.execute("UPDATE operations SET refunded_amount = 0 WHERE refunded_amount IS NULL")


def downgrade():
    schema = "public"

    if _column_exists("operations", "captured_amount", schema):
        op.drop_column("operations", "captured_amount", schema=schema)

    if _column_exists("operations", "refunded_amount", schema):
        op.drop_column("operations", "refunded_amount", schema=schema)

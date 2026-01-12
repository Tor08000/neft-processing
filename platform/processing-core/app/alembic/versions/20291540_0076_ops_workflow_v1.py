"""ops workflow v1

Revision ID: 20291540_0076_ops_workflow_v1
Revises: 20291530_0075_ops_escalations
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291540_0076_ops_workflow_v1"
down_revision = "20291530_0075_ops_escalations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ops_escalations", schema=SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("acked_by", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("ack_reason", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("closed_by", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("close_reason", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("unified_explain_snapshot_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("unified_explain_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass

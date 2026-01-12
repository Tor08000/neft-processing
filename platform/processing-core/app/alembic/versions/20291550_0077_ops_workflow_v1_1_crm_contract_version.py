"""ops workflow v1.1 reason codes + crm contract version

Revision ID: 20291550_0077_ops_workflow_v1_1_crm_contract_version
Revises: 20291540_0076_ops_workflow_v1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291550_0077_ops_workflow_v1_1_crm_contract_version"
down_revision = "20291540_0076_ops_workflow_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ops_escalations", schema=SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("ack_reason_code", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("close_reason_code", sa.String(length=64), nullable=True))

    with op.batch_alter_table("crm_contracts", schema=SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("crm_contract_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    pass

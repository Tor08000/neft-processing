"""ops escalation reason codes

Revision ID: 20291560_0078_ops_reason_codes
Revises: 20291550_0077_ops_workflow_v1_1_crm_contract_version
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291560_0078_ops_reason_codes"
down_revision = "20291550_0077_ops_workflow_v1_1_crm_contract_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ops_escalations", schema=SCHEMA) as batch_op:
        batch_op.add_column(sa.Column("reason_code", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE ops_escalations
        SET reason_code = CASE primary_reason
            WHEN 'LIMIT' THEN 'LIMIT_EXCEEDED'
            WHEN 'RISK' THEN 'RISK_BLOCK'
            WHEN 'LOGISTICS' THEN 'LOGISTICS_DEVIATION'
            WHEN 'MONEY' THEN 'MONEY_INVARIANT_VIOLATION'
            WHEN 'POLICY' THEN 'FEATURE_DISABLED'
            ELSE 'FEATURE_DISABLED'
        END
        """
    )

    with op.batch_alter_table("ops_escalations", schema=SCHEMA) as batch_op:
        batch_op.alter_column("reason_code", nullable=False)
        batch_op.create_index("ix_ops_escalations_reason_code", ["reason_code"])


def downgrade() -> None:
    pass

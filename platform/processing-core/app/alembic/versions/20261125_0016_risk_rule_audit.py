"""Add risk rule audits table

Revision ID: 20261125_0016_risk_rule_audit
Revises: 20261120_0015_risk_rules
Create Date: 2026-11-25 00:16:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20261125_0016_risk_rule_audit"
down_revision = "20261120_0015_risk_rules"
branch_labels = None
depends_on = None

risk_rule_audit_action_enum = sa.Enum(
    "CREATE",
    "UPDATE",
    "ENABLE",
    "DISABLE",
    name="riskruleauditaction",
)



def upgrade() -> None:
    risk_rule_audit_action_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "risk_rule_audits",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "rule_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("risk_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", risk_rule_audit_action_enum, nullable=False),
        sa.Column("old_value", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column("new_value", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column("performed_by", sa.String(length=256), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_risk_rule_audits_rule_id", "risk_rule_audits", ["rule_id"], unique=False)
    op.create_index("ix_risk_rule_audits_action", "risk_rule_audits", ["action"], unique=False)
    op.create_index("ix_risk_rule_audits_performed_at", "risk_rule_audits", ["performed_at"], unique=False)



def downgrade() -> None:
    op.drop_index("ix_risk_rule_audits_performed_at", table_name="risk_rule_audits")
    op.drop_index("ix_risk_rule_audits_action", table_name="risk_rule_audits")
    op.drop_index("ix_risk_rule_audits_rule_id", table_name="risk_rule_audits")
    op.drop_table("risk_rule_audits")
    risk_rule_audit_action_enum.drop(op.get_bind(), checkfirst=True)

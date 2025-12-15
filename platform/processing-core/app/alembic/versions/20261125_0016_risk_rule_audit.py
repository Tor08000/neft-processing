"""Add risk rule audits table

Revision ID: 20261125_0016_risk_rule_audit
Revises: 20261120_0015_risk_rules
Create Date: 2026-11-25 00:16:00.000000
"""

import logging

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
revision = "20261125_0016_risk_rule_audit"
down_revision = "20261120_0015_risk_rules"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


risk_rule_audit_action_enum = sa.Enum(
    "CREATE",
    "UPDATE",
    "ENABLE",
    "DISABLE",
    name="riskruleauditaction",
    create_type=False,
)



def upgrade() -> None:
    bind = op.get_bind()
    ensure_enum_type_exists(
        bind,
        type_name="riskruleauditaction",
        values=list(risk_rule_audit_action_enum.enums),
    )

    if table_exists(bind, "risk_rule_audits"):
        logger.info("Skipping creation of risk_rule_audits table: already exists")
        return

    op.create_table(
        "risk_rule_audits",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "rule_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("risk_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", risk_rule_audit_action_enum, nullable=False),
        sa.Column(
            "old_value",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("performed_by", sa.String(length=256), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    create_index_if_not_exists(bind, "ix_risk_rule_audits_rule_id", "risk_rule_audits", ["rule_id"])
    create_index_if_not_exists(bind, "ix_risk_rule_audits_action", "risk_rule_audits", ["action"])
    create_index_if_not_exists(
        bind, "ix_risk_rule_audits_performed_at", "risk_rule_audits", ["performed_at"]
    )



def downgrade() -> None:
    bind = op.get_bind()
    drop_index_if_exists(
        bind, "ix_risk_rule_audits_performed_at", table_name="risk_rule_audits"
    )
    drop_index_if_exists(bind, "ix_risk_rule_audits_action", table_name="risk_rule_audits")
    drop_index_if_exists(bind, "ix_risk_rule_audits_rule_id", table_name="risk_rule_audits")
    if table_exists(bind, "risk_rule_audits"):
        op.drop_table("risk_rule_audits")
    risk_rule_audit_action_enum.drop(bind, checkfirst=True)

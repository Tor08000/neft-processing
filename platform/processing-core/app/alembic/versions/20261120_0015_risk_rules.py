"""
Risk rules persistence tables

Revision ID: 20261120_0015_risk_rules
Revises: 20261101_0014_billing_summary_alignment
Create Date: 2026-11-20 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20261120_0015_risk_rules"
down_revision = "20261101_0014_billing_summary_alignment"
branch_labels = None
depends_on = None

risk_rule_scope_enum = sa.Enum(
    "GLOBAL",
    "CLIENT",
    "CARD",
    "TARIFF",
    "SEGMENT",
    name="riskrulescope",
)

risk_rule_action_enum = sa.Enum(
    "HARD_DECLINE",
    "SOFT_FLAG",
    "TARIFF_LIMIT",
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
    name="riskruleaction",
)


def upgrade() -> None:
    op.create_table(
        "risk_rules",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", risk_rule_scope_enum, nullable=False),
        sa.Column("subject_ref", sa.String(length=128), nullable=True),
        sa.Column("action", risk_rule_action_enum, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "dsl_payload",
            postgresql.JSONB(astext_type=sa.Text()) if op.get_bind().dialect.name == "postgresql" else sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "risk_rule_versions",
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "dsl_payload",
            postgresql.JSONB(astext_type=sa.Text()) if op.get_bind().dialect.name == "postgresql" else sa.JSON(),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("rule_id", "version", name="uq_risk_rule_version"),
    )

    op.create_index("ix_risk_rules_scope", "risk_rules", ["scope"], unique=False)
    op.create_index("ix_risk_rules_subject_ref", "risk_rules", ["subject_ref"], unique=False)
    op.create_index("ix_risk_rules_enabled", "risk_rules", ["enabled"], unique=False)
    op.create_index("ix_risk_rule_versions_rule_id", "risk_rule_versions", ["rule_id"], unique=False)
    op.create_index(
        "ix_risk_rule_versions_effective_from",
        "risk_rule_versions",
        ["effective_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risk_rule_versions_effective_from", table_name="risk_rule_versions")
    op.drop_index("ix_risk_rule_versions_rule_id", table_name="risk_rule_versions")
    op.drop_table("risk_rule_versions")

    op.drop_index("ix_risk_rules_enabled", table_name="risk_rules")
    op.drop_index("ix_risk_rules_subject_ref", table_name="risk_rules")
    op.drop_index("ix_risk_rules_scope", table_name="risk_rules")
    op.drop_table("risk_rules")

    risk_rule_action_enum.drop(op.get_bind(), checkfirst=True)
    risk_rule_scope_enum.drop(op.get_bind(), checkfirst=True)

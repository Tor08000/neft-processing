"""
Risk rules persistence tables

Revision ID: 20261120_0015_risk_rules
Revises: 20261101_0014_billing_summary_alignment
Create Date: 2026-11-20 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20261120_0015_risk_rules"
down_revision = "20261101_0014_billing_summary_alignment"
branch_labels = None
depends_on = None

RISK_RULE_SCOPE_VALUES = ["GLOBAL", "CLIENT", "CARD", "TARIFF", "SEGMENT"]

RISK_RULE_ACTION_VALUES = [
    "HARD_DECLINE",
    "SOFT_FLAG",
    "TARIFF_LIMIT",
    "LOW",
    "MEDIUM",
    "HIGH",
    "BLOCK",
    "MANUAL_REVIEW",
]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "riskrulescope", values=RISK_RULE_SCOPE_VALUES)
    ensure_pg_enum(bind, "riskruleaction", values=RISK_RULE_ACTION_VALUES)

    risk_rule_scope_enum = safe_enum(bind, "riskrulescope", RISK_RULE_SCOPE_VALUES)
    risk_rule_action_enum = safe_enum(bind, "riskruleaction", RISK_RULE_ACTION_VALUES)

    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if bind.dialect.name == "postgresql"
        else sa.JSON()
    )

    create_table_if_not_exists(
        bind,
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
            json_type,
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

    create_table_if_not_exists(
        bind,
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
            json_type,
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

    create_index_if_not_exists(bind, "ix_risk_rules_scope", "risk_rules", ["scope"], unique=False)
    create_index_if_not_exists(
        bind, "ix_risk_rules_subject_ref", "risk_rules", ["subject_ref"], unique=False
    )
    create_index_if_not_exists(bind, "ix_risk_rules_enabled", "risk_rules", ["enabled"], unique=False)
    create_index_if_not_exists(
        bind, "ix_risk_rule_versions_rule_id", "risk_rule_versions", ["rule_id"], unique=False
    )
    create_index_if_not_exists(
        bind,
        "ix_risk_rule_versions_effective_from",
        "risk_rule_versions",
        ["effective_from"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "risk_rule_versions"):
        drop_index_if_exists(bind, "ix_risk_rule_versions_effective_from")
        drop_index_if_exists(bind, "ix_risk_rule_versions_rule_id")
        drop_table_if_exists(bind, "risk_rule_versions")

    if table_exists(bind, "risk_rules"):
        drop_index_if_exists(bind, "ix_risk_rules_enabled")
        drop_index_if_exists(bind, "ix_risk_rules_subject_ref")
        drop_index_if_exists(bind, "ix_risk_rules_scope")
        drop_table_if_exists(bind, "risk_rules")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql("DROP TYPE IF EXISTS public.riskruleaction")
        bind.exec_driver_sql("DROP TYPE IF EXISTS public.riskrulescope")

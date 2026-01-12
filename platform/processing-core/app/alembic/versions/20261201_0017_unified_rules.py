"""
Unified rules DSL tables

Revision ID: 20261201_0017_unified_rules
Revises: 20261125_0016_risk_rule_audit
Create Date: 2026-12-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from db.schema import resolve_db_schema

revision = "20261201_0017_unified_rules"
down_revision = "20261125_0016_risk_rule_audit"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
SCHEMA_QUOTED = f'"{SCHEMA}"'

RULE_SCOPE_VALUES = [
    "API",
    "FLEET",
    "BILLING",
    "DOCS",
    "MARKETPLACE",
    "AUTH",
    "CRM",
    "GLOBAL",
]
RULE_METRIC_VALUES = [
    "COUNT",
    "AMOUNT",
    "RPS",
    "DECLINES",
    "EXPORTS",
    "CARDS_ISSUED",
]
RULE_POLICY_VALUES = [
    "ALLOW",
    "HARD_DECLINE",
    "SOFT_DECLINE",
    "REVIEW",
    "APPLY_LIMIT",
    "APPLY_DISCOUNT",
    "THROTTLE",
    "STEP_UP_AUTH",
]
RULE_SET_STATUS_VALUES = ["DRAFT", "PUBLISHED", "ACTIVE", "ROLLED_BACK", "ARCHIVED"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "unifiedrulescope", values=RULE_SCOPE_VALUES)
    ensure_pg_enum(bind, "unifiedrulemetric", values=RULE_METRIC_VALUES)
    ensure_pg_enum(bind, "unifiedrulepolicy", values=RULE_POLICY_VALUES)
    ensure_pg_enum(bind, "rulesetstatus", values=RULE_SET_STATUS_VALUES)

    scope_enum = safe_enum(bind, "unifiedrulescope", RULE_SCOPE_VALUES)
    metric_enum = safe_enum(bind, "unifiedrulemetric", RULE_METRIC_VALUES)
    policy_enum = safe_enum(bind, "unifiedrulepolicy", RULE_POLICY_VALUES)
    status_enum = safe_enum(bind, "rulesetstatus", RULE_SET_STATUS_VALUES)

    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if bind.dialect.name == "postgresql"
        else sa.JSON()
    )
    tags_type = (
        postgresql.ARRAY(sa.String())
        if bind.dialect.name == "postgresql"
        else sa.JSON()
    )

    create_table_if_not_exists(
        bind,
        "rule_set_versions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("scope", scope_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "parent_version_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("rule_set_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    create_table_if_not_exists(
        bind,
        "rule_set_active",
        sa.Column("scope", scope_enum, primary_key=True),
        sa.Column(
            "version_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    create_table_if_not_exists(
        bind,
        "rule_set_audits",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "version_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("performed_by", sa.String(length=256), nullable=True),
        sa.Column("payload", json_type, nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    create_table_if_not_exists(
        bind,
        "unified_rules",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column(
            "version_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("rule_set_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", scope_enum, nullable=False),
        sa.Column("selector", json_type, nullable=True),
        sa.Column("window", json_type, nullable=True),
        sa.Column("metric", metric_enum, nullable=True),
        sa.Column("value", json_type, nullable=True),
        sa.Column("policy", policy_enum, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("explain_template", sa.Text(), nullable=True),
        sa.Column("tags", tags_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("version_id", "code", name="uq_unified_rule_version_code"),
    )

    create_index_if_not_exists(bind, "ix_rule_set_versions_scope", "rule_set_versions", ["scope"])
    create_index_if_not_exists(bind, "ix_rule_set_versions_status", "rule_set_versions", ["status"])
    create_index_if_not_exists(bind, "ix_rule_set_active_version_id", "rule_set_active", ["version_id"])
    create_index_if_not_exists(bind, "ix_rule_set_audits_version_id", "rule_set_audits", ["version_id"])
    create_index_if_not_exists(bind, "ix_unified_rules_scope", "unified_rules", ["scope"])
    create_index_if_not_exists(bind, "ix_unified_rules_version_id", "unified_rules", ["version_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "unified_rules"):
        drop_index_if_exists(bind, "ix_unified_rules_version_id")
        drop_index_if_exists(bind, "ix_unified_rules_scope")
        drop_table_if_exists(bind, "unified_rules")

    if table_exists(bind, "rule_set_audits"):
        drop_index_if_exists(bind, "ix_rule_set_audits_version_id")
        drop_table_if_exists(bind, "rule_set_audits")

    if table_exists(bind, "rule_set_active"):
        drop_index_if_exists(bind, "ix_rule_set_active_version_id")
        drop_table_if_exists(bind, "rule_set_active")

    if table_exists(bind, "rule_set_versions"):
        drop_index_if_exists(bind, "ix_rule_set_versions_status")
        drop_index_if_exists(bind, "ix_rule_set_versions_scope")
        drop_table_if_exists(bind, "rule_set_versions")

    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.rulesetstatus")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.unifiedrulepolicy")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.unifiedrulemetric")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.unifiedrulescope")

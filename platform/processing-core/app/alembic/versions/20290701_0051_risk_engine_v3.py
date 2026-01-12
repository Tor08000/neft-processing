"""
Risk engine v3 entities

Revision ID: 20290701_0051_risk_engine_v3
Revises: 20290625_0050_fix_invoices_reconciliation_request_id_type
Create Date: 2029-07-01 00:00:00
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


# revision identifiers, used by Alembic.
revision = "20290701_0051_risk_engine_v3"
down_revision = "20290625_0050_fix_invoices_reconciliation_request_id_type"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
SCHEMA_QUOTED = f'"{SCHEMA}"'

RISK_SUBJECT_TYPES = ["PAYMENT", "INVOICE", "PAYOUT", "DOCUMENT", "EXPORT"]
RISK_DECISIONS = ["ALLOW", "ALLOW_WITH_REVIEW", "BLOCK", "ESCALATE"]
RISK_DECISION_ACTORS = ["SYSTEM", "ADMIN"]
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "risksubjecttype", values=RISK_SUBJECT_TYPES)
    ensure_pg_enum(bind, "riskdecision", values=RISK_DECISIONS)
    ensure_pg_enum(bind, "riskdecisionactor", values=RISK_DECISION_ACTORS)
    ensure_pg_enum(bind, "risklevel", values=RISK_LEVELS)

    subject_enum = safe_enum(bind, "risksubjecttype", RISK_SUBJECT_TYPES)
    decision_enum = safe_enum(bind, "riskdecision", RISK_DECISIONS)
    actor_enum = safe_enum(bind, "riskdecisionactor", RISK_DECISION_ACTORS)
    risk_level_enum = safe_enum(bind, "risklevel", RISK_LEVELS)

    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if bind.dialect.name == "postgresql"
        else sa.JSON()
    )

    create_table_if_not_exists(
        bind,
        "risk_threshold_sets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    create_table_if_not_exists(
        bind,
        "risk_thresholds",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("threshold_set_id", sa.String(length=64), nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("outcome", decision_enum, nullable=False),
        sa.Column("requires_manual_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
    )

    create_table_if_not_exists(
        bind,
        "risk_policies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("threshold_set_id", sa.String(length=64), nullable=False),
        sa.Column("model_selector", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    create_table_if_not_exists(
        bind,
        "risk_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("risk_level", risk_level_enum, nullable=False),
        sa.Column("threshold_set_id", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", decision_enum, nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("reasons", json_type, nullable=False),
        sa.Column("features_snapshot", json_type, nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_by", actor_enum, nullable=False),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), nullable=False),
    )

    create_index_if_not_exists(bind, "ix_risk_threshold_sets_subject", "risk_threshold_sets", ["subject_type"])
    create_index_if_not_exists(bind, "ix_risk_threshold_sets_active", "risk_threshold_sets", ["active"])

    create_index_if_not_exists(bind, "ix_risk_thresholds_set", "risk_thresholds", ["threshold_set_id"])
    create_index_if_not_exists(bind, "ix_risk_thresholds_priority", "risk_thresholds", ["priority"])
    create_index_if_not_exists(bind, "ix_risk_thresholds_subject", "risk_thresholds", ["subject_type"])
    create_index_if_not_exists(bind, "ix_risk_thresholds_active", "risk_thresholds", ["active"])

    create_index_if_not_exists(bind, "ix_risk_policies_subject", "risk_policies", ["subject_type"])
    create_index_if_not_exists(bind, "ix_risk_policies_active", "risk_policies", ["active"])
    create_index_if_not_exists(bind, "ix_risk_policies_priority", "risk_policies", ["priority"])
    create_index_if_not_exists(bind, "ix_risk_policies_tenant", "risk_policies", ["tenant_id"])
    create_index_if_not_exists(bind, "ix_risk_policies_client", "risk_policies", ["client_id"])

    create_index_if_not_exists(bind, "ix_risk_decisions_subject", "risk_decisions", ["subject_type", "subject_id"])
    create_index_if_not_exists(bind, "ix_risk_decisions_risk_level", "risk_decisions", ["risk_level"])
    create_index_if_not_exists(bind, "ix_risk_decisions_outcome", "risk_decisions", ["outcome"])
    create_index_if_not_exists(bind, "ix_risk_decisions_decided_at", "risk_decisions", ["decided_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "risk_decisions"):
        drop_index_if_exists(bind, "ix_risk_decisions_decided_at")
        drop_index_if_exists(bind, "ix_risk_decisions_outcome")
        drop_index_if_exists(bind, "ix_risk_decisions_risk_level")
        drop_index_if_exists(bind, "ix_risk_decisions_subject")
        drop_table_if_exists(bind, "risk_decisions")

    if table_exists(bind, "risk_policies"):
        drop_index_if_exists(bind, "ix_risk_policies_client")
        drop_index_if_exists(bind, "ix_risk_policies_tenant")
        drop_index_if_exists(bind, "ix_risk_policies_priority")
        drop_index_if_exists(bind, "ix_risk_policies_active")
        drop_index_if_exists(bind, "ix_risk_policies_subject")
        drop_table_if_exists(bind, "risk_policies")

    if table_exists(bind, "risk_thresholds"):
        drop_index_if_exists(bind, "ix_risk_thresholds_active")
        drop_index_if_exists(bind, "ix_risk_thresholds_subject")
        drop_index_if_exists(bind, "ix_risk_thresholds_priority")
        drop_index_if_exists(bind, "ix_risk_thresholds_set")
        drop_table_if_exists(bind, "risk_thresholds")

    if table_exists(bind, "risk_threshold_sets"):
        drop_index_if_exists(bind, "ix_risk_threshold_sets_active")
        drop_index_if_exists(bind, "ix_risk_threshold_sets_subject")
        drop_table_if_exists(bind, "risk_threshold_sets")

    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.riskdecisionactor")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.riskdecision")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.risksubjecttype")
        bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA_QUOTED}.risklevel")

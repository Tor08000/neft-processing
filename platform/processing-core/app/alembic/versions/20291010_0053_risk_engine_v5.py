"""
Risk engine v5 shadow mode tables.

Revision ID: 20291010_0053_risk_engine_v5
Revises: 20291001_0052_risk_engine_v4
Create Date: 2029-10-10 00:00:00
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


revision = "20291010_0053_risk_engine_v5"
down_revision = "20291001_0052_risk_engine_v4"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

SUBJECT_TYPES = ["PAYMENT", "INVOICE", "PAYOUT", "DOCUMENT", "EXPORT"]
RISK_DECISIONS = ["ALLOW", "ALLOW_WITH_REVIEW", "BLOCK", "ESCALATE"]
LABELS = ["FRAUD", "NOT_FRAUD", "UNKNOWN"]
LABEL_SOURCES = ["OVERRIDE", "DISPUTE", "CHARGEBACK", "ANOMALY"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "risksubjecttype", values=SUBJECT_TYPES)
    ensure_pg_enum(bind, "riskdecision", values=RISK_DECISIONS)
    ensure_pg_enum(bind, "riskv5label", values=LABELS)
    ensure_pg_enum(bind, "riskv5labelsource", values=LABEL_SOURCES)

    subject_enum = safe_enum(bind, "risksubjecttype", SUBJECT_TYPES)
    decision_enum = safe_enum(bind, "riskdecision", RISK_DECISIONS)
    label_enum = safe_enum(bind, "riskv5label", LABELS)
    label_source_enum = safe_enum(bind, "riskv5labelsource", LABEL_SOURCES)

    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()

    create_table_if_not_exists(
        bind,
        "risk_v5_shadow_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("v4_score", sa.Integer(), nullable=True),
        sa.Column("v4_outcome", decision_enum, nullable=False),
        sa.Column("v4_policy_id", sa.String(length=64), nullable=True),
        sa.Column("v4_threshold_set_id", sa.String(length=64), nullable=True),
        sa.Column("v5_score", sa.Integer(), nullable=True),
        sa.Column("v5_predicted_outcome", sa.String(length=32), nullable=True),
        sa.Column("v5_model_version", sa.String(length=64), nullable=True),
        sa.Column("v5_selector", sa.String(length=64), nullable=True),
        sa.Column("features_schema_version", sa.String(length=32), nullable=False),
        sa.Column("features_hash", sa.String(length=64), nullable=False),
        sa.Column("features_snapshot", json_type, nullable=False),
        sa.Column("explain", json_type, nullable=True),
        sa.Column("error", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(bind, "ix_risk_v5_shadow_decisions_decision", "risk_v5_shadow_decisions", ["decision_id"])
    create_index_if_not_exists(bind, "ix_risk_v5_shadow_decisions_subject", "risk_v5_shadow_decisions", ["subject_type"])
    create_index_if_not_exists(bind, "ix_risk_v5_shadow_decisions_created", "risk_v5_shadow_decisions", ["created_at"])

    create_table_if_not_exists(
        bind,
        "risk_v5_ab_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("bucket", sa.String(length=1), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(bind, "ix_risk_v5_ab_assignments_subject", "risk_v5_ab_assignments", ["subject_type"])
    create_index_if_not_exists(bind, "ix_risk_v5_ab_assignments_client", "risk_v5_ab_assignments", ["client_id"])
    create_index_if_not_exists(bind, "ix_risk_v5_ab_assignments_tenant", "risk_v5_ab_assignments", ["tenant_id"])
    create_index_if_not_exists(bind, "ix_risk_v5_ab_assignments_active", "risk_v5_ab_assignments", ["active"])

    create_table_if_not_exists(
        bind,
        "risk_v5_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("label", label_enum, nullable=False),
        sa.Column("label_source", label_source_enum, nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(bind, "ix_risk_v5_labels_decision", "risk_v5_labels", ["decision_id"])
    create_index_if_not_exists(bind, "ix_risk_v5_labels_subject", "risk_v5_labels", ["subject_type", "subject_id"])


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "risk_v5_labels"):
        drop_index_if_exists(bind, "ix_risk_v5_labels_subject")
        drop_index_if_exists(bind, "ix_risk_v5_labels_decision")
        drop_table_if_exists(bind, "risk_v5_labels")

    if table_exists(bind, "risk_v5_shadow_decisions"):
        drop_index_if_exists(bind, "ix_risk_v5_shadow_decisions_created")
        drop_index_if_exists(bind, "ix_risk_v5_shadow_decisions_subject")
        drop_index_if_exists(bind, "ix_risk_v5_shadow_decisions_decision")
        drop_table_if_exists(bind, "risk_v5_shadow_decisions")

    if table_exists(bind, "risk_v5_ab_assignments"):
        drop_index_if_exists(bind, "ix_risk_v5_ab_assignments_active")
        drop_index_if_exists(bind, "ix_risk_v5_ab_assignments_tenant")
        drop_index_if_exists(bind, "ix_risk_v5_ab_assignments_client")
        drop_index_if_exists(bind, "ix_risk_v5_ab_assignments_subject")
        drop_table_if_exists(bind, "risk_v5_ab_assignments")

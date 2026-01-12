"""
Risk engine v4 thresholds and training snapshots.

Revision ID: 20291001_0052_risk_engine_v4
Revises: 20290701_0051_risk_engine_v3
Create Date: 2029-10-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from db.schema import resolve_db_schema


revision = "20291001_0052_risk_engine_v4"
down_revision = "20290701_0051_risk_engine_v3"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
SCHEMA_QUOTED = f'"{SCHEMA}"'

THRESHOLD_SCOPES = ["GLOBAL", "TENANT", "CLIENT"]
THRESHOLD_ACTIONS = ["PAYMENT", "INVOICE", "PAYOUT", "EXPORT", "DOCUMENT_FINALIZE"]


def upgrade() -> None:
    bind = op.get_bind()

    ensure_pg_enum(bind, "riskthresholdscope", values=THRESHOLD_SCOPES)
    ensure_pg_enum(bind, "riskthresholdaction", values=THRESHOLD_ACTIONS)

    scope_enum = safe_enum(bind, "riskthresholdscope", THRESHOLD_SCOPES)
    action_enum = safe_enum(bind, "riskthresholdaction", THRESHOLD_ACTIONS)

    if table_exists(bind, "risk_threshold_sets"):
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("scope", scope_enum, nullable=False, server_default="GLOBAL"))
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("action", action_enum, nullable=False, server_default="PAYMENT"))
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("block_threshold", sa.Integer(), nullable=False, server_default="90"))
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("review_threshold", sa.Integer(), nullable=False, server_default="70"))
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("allow_threshold", sa.Integer(), nullable=False, server_default="0"))
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("currency", sa.String(length=3), nullable=True))
        _add_column_if_missing(
            bind,
            "risk_threshold_sets",
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        _add_column_if_missing(
            bind,
            "risk_threshold_sets",
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        )
        _add_column_if_missing(bind, "risk_threshold_sets", sa.Column("created_by", sa.String(length=64), nullable=True))

    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if bind.dialect.name == "postgresql"
        else sa.JSON()
    )

    create_table_if_not_exists(
        bind,
        "risk_training_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("features_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("features_hash", sa.String(length=64), nullable=False),
        sa.Column("context", json_type, nullable=False),
        sa.Column("policy", json_type, nullable=True),
        sa.Column("thresholds", json_type, nullable=False),
        sa.Column("features", json_type, nullable=False),
        sa.Column("post_factum_outcome", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(bind, "ix_risk_training_snapshots_decision", "risk_training_snapshots", ["decision_id"])
    create_index_if_not_exists(bind, "ix_risk_training_snapshots_created", "risk_training_snapshots", ["created_at"])
    create_index_if_not_exists(bind, "ix_risk_threshold_sets_scope", "risk_threshold_sets", ["scope"])
    create_index_if_not_exists(bind, "ix_risk_threshold_sets_action", "risk_threshold_sets", ["action"])


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "risk_training_snapshots"):
        drop_index_if_exists(bind, "ix_risk_training_snapshots_created")
        drop_index_if_exists(bind, "ix_risk_training_snapshots_decision")
        drop_table_if_exists(bind, "risk_training_snapshots")

    if table_exists(bind, "risk_threshold_sets"):
        drop_index_if_exists(bind, "ix_risk_threshold_sets_action")
        drop_index_if_exists(bind, "ix_risk_threshold_sets_scope")


def _add_column_if_missing(bind, table: str, column: sa.Column) -> None:
    if not column_exists(bind, table, column.name):
        op.add_column(table, column, schema=SCHEMA)

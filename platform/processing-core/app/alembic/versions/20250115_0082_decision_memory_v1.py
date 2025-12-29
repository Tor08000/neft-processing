"""decision memory v1

Revision ID: 20250115_0082_decision_memory_v1
Revises: 20291590_0081_fleet_control_v3
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_expr_index_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    table_exists,
)
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20250115_0082_decision_memory_v1"
down_revision = "20291590_0081_fleet_control_v3"
branch_labels = None
depends_on = None

DECISION_MEMORY_ENTITY_TYPE = ["DRIVER", "VEHICLE", "STATION", "CLIENT"]
DECISION_MEMORY_EFFECT_LABEL = ["IMPROVED", "NO_CHANGE", "WORSE", "UNKNOWN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "decision_memory_entity_type", DECISION_MEMORY_ENTITY_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "decision_memory_effect_label", DECISION_MEMORY_EFFECT_LABEL, schema=SCHEMA)

    if not table_exists(bind, "decision_outcomes", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "decision_outcomes",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(length=64), nullable=True),
                sa.Column(
                    "entity_type",
                    postgresql.ENUM(
                        *DECISION_MEMORY_ENTITY_TYPE,
                        name="decision_memory_entity_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("entity_id", sa.String(length=64), nullable=False),
                sa.Column("insight_id", sa.String(36), nullable=True),
                sa.Column("applied_action_id", sa.String(36), nullable=True),
                sa.Column("action_code", sa.String(length=128), nullable=False),
                sa.Column("bundle_code", sa.String(length=64), nullable=True),
                sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column(
                    "effect_label",
                    postgresql.ENUM(
                        *DECISION_MEMORY_EFFECT_LABEL,
                        name="decision_memory_effect_label",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("effect_delta", sa.JSON(), nullable=True),
                sa.Column("confidence_at_apply", sa.Float, nullable=True),
                sa.Column("context", sa.JSON(), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.UniqueConstraint("applied_action_id", name="uq_decision_outcomes_applied_action"),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        create_index_if_not_exists(bind, "ix_decision_outcomes_tenant", "decision_outcomes", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(
            bind,
            "ix_decision_outcomes_entity",
            "decision_outcomes",
            ["entity_type", "entity_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind, "ix_decision_outcomes_action", "decision_outcomes", ["action_code"], schema=SCHEMA
        )
        create_index_if_not_exists(
            bind, "ix_decision_outcomes_applied_at", "decision_outcomes", ["applied_at"], schema=SCHEMA
        )
        create_unique_expr_index_if_not_exists(
            bind,
            "uq_decision_outcomes_scope_day",
            "decision_outcomes",
            "(tenant_id, entity_type, entity_id, action_code, (applied_at::date))",
            schema=SCHEMA,
        )

    if not table_exists(bind, "decision_action_stats_daily", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "decision_action_stats_daily",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(length=64), nullable=True),
                sa.Column("action_code", sa.String(length=128), nullable=False),
                sa.Column(
                    "entity_type",
                    postgresql.ENUM(
                        *DECISION_MEMORY_ENTITY_TYPE,
                        name="decision_memory_entity_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("day", sa.Date, nullable=False),
                sa.Column("applied_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("improved_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("no_change_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("worse_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("weighted_success", sa.Float, nullable=False, server_default="0"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_decision_action_stats_daily_scope",
            "decision_action_stats_daily",
            ["tenant_id", "action_code", "entity_type", "day", "client_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_decision_action_stats_daily_tenant",
            "decision_action_stats_daily",
            ["tenant_id"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_decision_action_stats_daily_action",
            "decision_action_stats_daily",
            ["action_code"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_decision_action_stats_daily_entity",
            "decision_action_stats_daily",
            ["entity_type"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_decision_action_stats_daily_day",
            "decision_action_stats_daily",
            ["day"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass

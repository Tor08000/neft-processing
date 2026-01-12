"""fleet control v3

Revision ID: 20291590_0081_fleet_control_v3
Revises: 20291580_0080_fleet_intelligence_trends_v2
Create Date: 2029-05-90 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_table_if_not_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291590_0081_fleet_control_v3"
down_revision = "20291580_0080_fleet_intelligence_trends_v2"
branch_labels = None
depends_on = None

INSIGHT_TYPE = [
    "DRIVER_BEHAVIOR_DEGRADING",
    "STATION_TRUST_DEGRADING",
    "VEHICLE_EFFICIENCY_DEGRADING",
]
INSIGHT_ENTITY_TYPE = ["DRIVER", "VEHICLE", "STATION"]
INSIGHT_SEVERITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
INSIGHT_STATUS = [
    "OPEN",
    "ACKED",
    "ACTION_PLANNED",
    "ACTION_APPLIED",
    "MONITORING",
    "RESOLVED",
    "IGNORED",
]
ACTION_CODE = [
    "SUGGEST_LIMIT_PROFILE_SAFE",
    "SUGGEST_RESTRICT_NIGHT_FUELING",
    "SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL",
    "SUGGEST_EXCLUDE_STATION_FROM_ROUTES",
    "SUGGEST_VEHICLE_DIAGNOSTIC",
]
ACTION_TARGET = ["CRM", "LOGISTICS", "OPS"]
SUGGESTED_STATUS = ["PROPOSED", "APPROVED", "REJECTED", "APPLIED"]
APPLIED_STATUS = ["SUCCESS", "FAILED"]
EFFECT_LABEL = ["IMPROVED", "NO_CHANGE", "WORSE"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fi_insight_type", INSIGHT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_insight_entity_type", INSIGHT_ENTITY_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_insight_severity", INSIGHT_SEVERITY, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_insight_status", INSIGHT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_action_code", ACTION_CODE, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_action_target_system", ACTION_TARGET, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_suggested_action_status", SUGGESTED_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_applied_action_status", APPLIED_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_action_effect_label", EFFECT_LABEL, schema=SCHEMA)

    if not table_exists(bind, "fi_insights", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_insights",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column(
                    "insight_type",
                    postgresql.ENUM(*INSIGHT_TYPE, name="fi_insight_type", schema=SCHEMA, create_type=False),
                    nullable=False,
                ),
                sa.Column(
                    "entity_type",
                    postgresql.ENUM(
                        *INSIGHT_ENTITY_TYPE,
                        name="fi_insight_entity_type",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column(
                    "severity",
                    postgresql.ENUM(*INSIGHT_SEVERITY, name="fi_insight_severity", schema=SCHEMA, create_type=False),
                    nullable=False,
                ),
                sa.Column(
                    "status",
                    postgresql.ENUM(*INSIGHT_STATUS, name="fi_insight_status", schema=SCHEMA, create_type=False),
                    nullable=False,
                ),
                sa.Column(
                    "primary_reason",
                    postgresql.ENUM(
                        "LIMIT",
                        "RISK",
                        "LOGISTICS",
                        "MONEY",
                        "POLICY",
                        "UNKNOWN",
                        name="ops_escalation_primary_reason",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("summary", sa.Text, nullable=True),
                sa.Column("evidence", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
                sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("acked_by", sa.String(64), nullable=True),
                sa.Column("ack_reason", sa.Text, nullable=True),
                sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("resolved_by", sa.String(64), nullable=True),
                sa.Column("resolve_reason", sa.Text, nullable=True),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint(
                    "tenant_id",
                    "insight_type",
                    "entity_type",
                    "entity_id",
                    "window_days",
                    "created_at",
                    name="uq_fi_insight_scope_created",
                ),
            ),
        )
        op.create_index("ix_fi_insights_client_status", "fi_insights", ["client_id", "status"], schema=SCHEMA)

    if not table_exists(bind, "fi_suggested_actions", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_suggested_actions",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("insight_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column(
                    "action_code",
                    postgresql.ENUM(*ACTION_CODE, name="fi_action_code", schema=SCHEMA, create_type=False),
                    nullable=False,
                ),
                sa.Column(
                    "target_system",
                    postgresql.ENUM(
                        *ACTION_TARGET,
                        name="fi_action_target_system",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("payload", sa.JSON, nullable=True),
                sa.Column(
                    "status",
                    postgresql.ENUM(
                        *SUGGESTED_STATUS,
                        name="fi_suggested_action_status",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
                sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("approved_by", sa.String(64), nullable=True),
                sa.Column("approve_reason", sa.Text, nullable=True),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("insight_id", "action_code", name="uq_fi_suggested_action_code"),
                sa.ForeignKeyConstraint(["insight_id"], [f"{SCHEMA}.fi_insights.id"]),
            ),
        )
        op.create_index("ix_fi_suggested_actions_status", "fi_suggested_actions", ["status"], schema=SCHEMA)

    if not table_exists(bind, "fi_applied_actions", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_applied_actions",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("insight_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column(
                    "action_code",
                    postgresql.ENUM(*ACTION_CODE, name="fi_action_code", schema=SCHEMA, create_type=False),
                    nullable=False,
                ),
                sa.Column("applied_by", sa.String(64), nullable=True),
                sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
                sa.Column("reason_code", sa.String(64), nullable=False),
                sa.Column("reason_text", sa.Text, nullable=True),
                sa.Column("before_state", sa.JSON, nullable=True),
                sa.Column("after_state", sa.JSON, nullable=True),
                sa.Column(
                    "status",
                    postgresql.ENUM(
                        *APPLIED_STATUS,
                        name="fi_applied_action_status",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("error_message", sa.Text, nullable=True),
                sa.PrimaryKeyConstraint("id"),
                sa.ForeignKeyConstraint(["insight_id"], [f"{SCHEMA}.fi_insights.id"]),
            ),
        )

    if not table_exists(bind, "fi_action_effects", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_action_effects",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("applied_action_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("measured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column("baseline", sa.JSON, nullable=True),
                sa.Column("current", sa.JSON, nullable=True),
                sa.Column("delta", sa.JSON, nullable=True),
                sa.Column(
                    "effect_label",
                    postgresql.ENUM(
                        *EFFECT_LABEL,
                        name="fi_action_effect_label",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("summary", sa.Text, nullable=True),
                sa.PrimaryKeyConstraint("id"),
                sa.ForeignKeyConstraint(["applied_action_id"], [f"{SCHEMA}.fi_applied_actions.id"]),
            ),
        )


def downgrade() -> None:
    pass

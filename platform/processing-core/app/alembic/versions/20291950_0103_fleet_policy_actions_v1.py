"""fleet policy actions v1.

Revision ID: 20291950_0103_fleet_policy_actions_v1
Revises: 20291940_0102_marketplace_contracts_v1
Create Date: 2025-02-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    DB_SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    ensure_pg_enum_value,
    safe_enum,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20291950_0103_fleet_policy_actions_v1"
down_revision = "20291940_0102_marketplace_contracts_v1"
branch_labels = None
depends_on = None

FLEET_ACTION_POLICY_SCOPE_TYPE = ["client", "group", "card"]
FLEET_ACTION_TRIGGER_TYPE = ["LIMIT_BREACH", "ANOMALY"]
FLEET_ACTION_BREACH_KIND = ["SOFT", "HARD", "ANY"]
FLEET_ACTION_POLICY_ACTION = ["NONE", "NOTIFY_ONLY", "AUTO_BLOCK_CARD", "ESCALATE_CASE"]
FLEET_POLICY_EXECUTION_STATUS = ["TRIGGERED", "APPLIED", "SKIPPED", "FAILED"]
FUEL_CARD_STATUS_ACTOR_TYPE = ["system", "user"]
FLEET_NOTIFICATION_SEVERITY = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

CASE_EVENT_VALUES = [
    "FUEL_CARD_UNBLOCKED",
    "FLEET_POLICY_ACTION_APPLIED",
    "FLEET_POLICY_ACTION_FAILED",
    "FLEET_ESCALATION_CASE_CREATED",
    "FLEET_ACTION_POLICY_CREATED",
    "FLEET_ACTION_POLICY_DISABLED",
]

FLEET_NOTIFICATION_EVENT_VALUES = ["POLICY_ACTION"]
FUEL_ANOMALY_VALUES = ["REPEATED_BREACH"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fleet_action_policy_scope_type", FLEET_ACTION_POLICY_SCOPE_TYPE, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_action_trigger_type", FLEET_ACTION_TRIGGER_TYPE, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_action_policy_breach_kind", FLEET_ACTION_BREACH_KIND, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_action_policy_action", FLEET_ACTION_POLICY_ACTION, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_policy_execution_status", FLEET_POLICY_EXECUTION_STATUS, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fuel_card_status_actor_type", FUEL_CARD_STATUS_ACTOR_TYPE, schema=DB_SCHEMA)
    ensure_pg_enum(bind, "fleet_notification_severity", FLEET_NOTIFICATION_SEVERITY, schema=DB_SCHEMA)

    for value in CASE_EVENT_VALUES:
        ensure_pg_enum_value(bind, "case_event_type", value, schema=DB_SCHEMA)

    op.execute(
        f"""
        DO $$
        BEGIN
            CREATE TYPE {DB_SCHEMA}.fleet_notification_event_type AS ENUM ('POLICY_ACTION');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
        """
    )

    for value in FLEET_NOTIFICATION_EVENT_VALUES:
        ensure_pg_enum_value(bind, "fleet_notification_event_type", value, schema=DB_SCHEMA)

    for value in FUEL_ANOMALY_VALUES:
        ensure_pg_enum_value(bind, "fuel_anomaly_type", value, schema=DB_SCHEMA)

    if table_exists(bind, "fleet_action_policies", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "fleet_action_policies",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("scope_type", safe_enum(bind, "fleet_action_policy_scope_type", FLEET_ACTION_POLICY_SCOPE_TYPE, schema=DB_SCHEMA), nullable=False),
            sa.Column("scope_id", sa.String(36), nullable=True),
            sa.Column("trigger_type", safe_enum(bind, "fleet_action_trigger_type", FLEET_ACTION_TRIGGER_TYPE, schema=DB_SCHEMA), nullable=False),
            sa.Column("trigger_severity_min", safe_enum(bind, "fleet_notification_severity", FLEET_NOTIFICATION_SEVERITY, schema=DB_SCHEMA), nullable=False),
            sa.Column("breach_kind", safe_enum(bind, "fleet_action_policy_breach_kind", FLEET_ACTION_BREACH_KIND, schema=DB_SCHEMA), nullable=True),
            sa.Column("action", safe_enum(bind, "fleet_action_policy_action", FLEET_ACTION_POLICY_ACTION, schema=DB_SCHEMA), nullable=False),
            sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("audit_event_id", sa.String(36), nullable=True),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fleet_action_policies_client_trigger_active",
            "fleet_action_policies",
            ["client_id", "trigger_type", "active"],
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fleet_action_policies_scope_active",
            "fleet_action_policies",
            ["scope_type", "scope_id", "active"],
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "fleet_policy_executions", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "fleet_policy_executions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("policy_id", sa.String(36), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("event_id", sa.String(36), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("status", safe_enum(bind, "fleet_policy_execution_status", FLEET_POLICY_EXECUTION_STATUS, schema=DB_SCHEMA), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("dedupe_key", sa.String(256), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("audit_event_id", sa.String(36), nullable=True),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fleet_policy_executions_client_created",
            "fleet_policy_executions",
            ["client_id", "created_at"],
            schema=DB_SCHEMA,
        )

    if table_exists(bind, "fuel_card_status_events", schema=DB_SCHEMA) is False:
        create_table_if_not_exists(
            bind,
            "fuel_card_status_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("card_id", sa.String(36), nullable=False),
            sa.Column("from_status", safe_enum(bind, "fuel_card_status", ["ACTIVE", "BLOCKED", "LOST", "EXPIRED", "CLOSED"], schema=DB_SCHEMA), nullable=True),
            sa.Column("to_status", safe_enum(bind, "fuel_card_status", ["ACTIVE", "BLOCKED", "LOST", "EXPIRED", "CLOSED"], schema=DB_SCHEMA), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("actor_type", safe_enum(bind, "fuel_card_status_actor_type", FUEL_CARD_STATUS_ACTOR_TYPE, schema=DB_SCHEMA), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("audit_event_id", sa.String(36), nullable=True),
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_card_status_events_card_created",
            "fuel_card_status_events",
            ["card_id", "created_at"],
            schema=DB_SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_card_status_events_client_created",
            "fuel_card_status_events",
            ["client_id", "created_at"],
            schema=DB_SCHEMA,
        )

    if column_exists(bind, "cases", "case_source_ref_type", schema=DB_SCHEMA) is False:
        op.add_column("cases", sa.Column("case_source_ref_type", sa.String(64), nullable=True), schema=DB_SCHEMA)
    if column_exists(bind, "cases", "case_source_ref_id", schema=DB_SCHEMA) is False:
        op.add_column("cases", sa.Column("case_source_ref_id", sa.String(36), nullable=True), schema=DB_SCHEMA)
        create_index_if_not_exists(
            bind,
            "ix_cases_source_ref",
            "cases",
            ["case_source_ref_type", "case_source_ref_id"],
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if column_exists(bind, "cases", "case_source_ref_id", schema=DB_SCHEMA):
        op.drop_column("cases", "case_source_ref_id", schema=DB_SCHEMA)
    if column_exists(bind, "cases", "case_source_ref_type", schema=DB_SCHEMA):
        op.drop_column("cases", "case_source_ref_type", schema=DB_SCHEMA)

    if table_exists(bind, "fuel_card_status_events", schema=DB_SCHEMA):
        op.drop_table("fuel_card_status_events", schema=DB_SCHEMA)
    if table_exists(bind, "fleet_policy_executions", schema=DB_SCHEMA):
        op.drop_table("fleet_policy_executions", schema=DB_SCHEMA)
    if table_exists(bind, "fleet_action_policies", schema=DB_SCHEMA):
        op.drop_table("fleet_action_policies", schema=DB_SCHEMA)

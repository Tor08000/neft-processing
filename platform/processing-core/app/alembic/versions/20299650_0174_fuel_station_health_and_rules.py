"""add station health fields and station risk default rule

Revision ID: 20299650_0174_fuel_station_health_and_rules
Revises: 20299640_0173_fuel_station_risk_zone
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, constraint_exists, index_exists, table_exists

revision = "20299650_0174_fuel_station_health_and_rules"
down_revision = "20299640_0173_fuel_station_risk_zone"
branch_labels = None
depends_on = None

_HEALTH_CHECK_NAME = "ck_fuel_stations_health_status_allowed"
_HEALTH_SOURCE_CHECK_NAME = "ck_fuel_stations_health_source_allowed"
_RULE_UNIQUE_NAME = "uq_rules_scope_subject_name"


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "fuel_stations", "health_status", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("health_status", sa.String(length=16), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "last_heartbeat", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "health_reason", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("health_reason", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "health_updated_at", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("health_updated_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "health_updated_by", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("health_updated_by", sa.String(length=256), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "health_source", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("health_source", sa.String(length=16), nullable=True), schema=DB_SCHEMA)

    if not constraint_exists(bind, "fuel_stations", _HEALTH_CHECK_NAME, schema=DB_SCHEMA):
        op.create_check_constraint(
            _HEALTH_CHECK_NAME,
            "fuel_stations",
            "health_status IS NULL OR health_status IN ('ONLINE', 'DEGRADED', 'OFFLINE')",
            schema=DB_SCHEMA,
        )
    if not constraint_exists(bind, "fuel_stations", _HEALTH_SOURCE_CHECK_NAME, schema=DB_SCHEMA):
        op.create_check_constraint(
            _HEALTH_SOURCE_CHECK_NAME,
            "fuel_stations",
            "health_source IS NULL OR health_source IN ('MANUAL', 'INTEGRATION', 'TERMINAL', 'SYSTEM')",
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_fuel_stations_health_status", schema=DB_SCHEMA):
        op.create_index("ix_fuel_stations_health_status", "fuel_stations", ["health_status"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "ix_fuel_stations_last_heartbeat", schema=DB_SCHEMA):
        op.create_index("ix_fuel_stations_last_heartbeat", "fuel_stations", ["last_heartbeat"], unique=False, schema=DB_SCHEMA)

    if not table_exists(bind, "rules", schema=DB_SCHEMA):
        op.create_table(
            "rules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("scope", sa.String(length=32), nullable=False),
            sa.Column("subject_id", sa.String(length=128), nullable=False),
            sa.Column("selector", sa.JSON(), nullable=True),
            sa.Column("window", sa.String(length=32), nullable=True),
            sa.Column("metric", sa.String(length=32), nullable=True),
            sa.Column("policy", sa.String(length=32), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("name", sa.String(length=128), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.UniqueConstraint("scope", "subject_id", "name", name=_RULE_UNIQUE_NAME),
            schema=DB_SCHEMA,
        )

    op.execute(
        sa.text(
            f"""
            INSERT INTO {DB_SCHEMA}.rules (scope, subject_id, selector, "window", metric, policy, meta, priority, enabled, system, name, description)
            SELECT 'TENANT', 'default', :selector, 'PER_TXN', 'FLAG', 'SOFT_DECLINE', :meta, 10, true, true,
                   'default_station_risk_red_soft_decline',
                   'System default: STATION_RISK_RED -> SOFT_DECLINE + manual review'
            WHERE NOT EXISTS (
                SELECT 1 FROM {DB_SCHEMA}.rules
                WHERE scope='TENANT' AND subject_id='default' AND name='default_station_risk_red_soft_decline'
            )
            """
        ).bindparams(
            sa.bindparam("selector", value={"risk_tags": ["STATION_RISK_RED"]}, type_=sa.JSON()),
            sa.bindparam("meta", value={"manual_review": True, "reason_code": "STATION_RISK_RED"}, type_=sa.JSON()),
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "rules", schema=DB_SCHEMA):
        op.execute(
            f"DELETE FROM {DB_SCHEMA}.rules WHERE scope='TENANT' AND subject_id='default' AND name='default_station_risk_red_soft_decline'"
        )

    if index_exists(bind, "ix_fuel_stations_last_heartbeat", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_stations_last_heartbeat", table_name="fuel_stations", schema=DB_SCHEMA)
    if index_exists(bind, "ix_fuel_stations_health_status", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_stations_health_status", table_name="fuel_stations", schema=DB_SCHEMA)

    if constraint_exists(bind, "fuel_stations", _HEALTH_SOURCE_CHECK_NAME, schema=DB_SCHEMA):
        op.drop_constraint(_HEALTH_SOURCE_CHECK_NAME, "fuel_stations", type_="check", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_stations", _HEALTH_CHECK_NAME, schema=DB_SCHEMA):
        op.drop_constraint(_HEALTH_CHECK_NAME, "fuel_stations", type_="check", schema=DB_SCHEMA)

    for column_name in ["health_source", "health_updated_by", "health_updated_at", "health_reason", "last_heartbeat", "health_status"]:
        if column_exists(bind, "fuel_stations", column_name, schema=DB_SCHEMA):
            op.drop_column("fuel_stations", column_name, schema=DB_SCHEMA)

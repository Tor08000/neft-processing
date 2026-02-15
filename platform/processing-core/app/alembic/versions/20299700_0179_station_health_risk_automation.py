"""station health and risk automation metadata

Revision ID: 20299700_0179_station_health_risk_automation
Revises: 20299690_0178_geo_tiles_daily_overlays
Create Date: 2026-02-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, constraint_exists, index_exists, table_exists

revision = "20299700_0179_station_health_risk_automation"
down_revision = "20299690_0178_geo_tiles_daily_overlays"
branch_labels = None
depends_on = None

_HEALTH_LOCK = "ck_fuel_stations_health_manual_until_requires_lock"
_RISK_LOCK = "ck_fuel_stations_risk_manual_until_requires_lock"
_EVENT_TYPE_CHECK = "ck_ops_station_events_type"


def upgrade() -> None:
    bind = op.get_bind()

    for name, default in (
        ("health_manual_lock", sa.text("false")),
        ("health_auto_enabled", sa.text("true")),
        ("risk_manual_lock", sa.text("false")),
        ("risk_auto_enabled", sa.text("true")),
    ):
        if not column_exists(bind, "fuel_stations", name, schema=DB_SCHEMA):
            op.add_column("fuel_stations", sa.Column(name, sa.Boolean(), nullable=False, server_default=default), schema=DB_SCHEMA)

    for name in ("health_manual_until", "health_last_auto_at", "risk_manual_until", "risk_last_auto_at"):
        if not column_exists(bind, "fuel_stations", name, schema=DB_SCHEMA):
            op.add_column("fuel_stations", sa.Column(name, sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)

    if not constraint_exists(bind, "fuel_stations", _HEALTH_LOCK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _HEALTH_LOCK,
            "fuel_stations",
            "health_manual_until IS NULL OR health_manual_lock = true",
            schema=DB_SCHEMA,
        )

    if not constraint_exists(bind, "fuel_stations", _RISK_LOCK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _RISK_LOCK,
            "fuel_stations",
            "risk_manual_until IS NULL OR risk_manual_lock = true",
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_fuel_stations_health_manual_lock", schema=DB_SCHEMA):
        op.create_index("ix_fuel_stations_health_manual_lock", "fuel_stations", ["health_manual_lock"], unique=False, schema=DB_SCHEMA)
    if not index_exists(bind, "ix_fuel_stations_risk_manual_lock", schema=DB_SCHEMA):
        op.create_index("ix_fuel_stations_risk_manual_lock", "fuel_stations", ["risk_manual_lock"], unique=False, schema=DB_SCHEMA)

    if not table_exists(bind, "ops_station_events", schema=DB_SCHEMA):
        op.create_table(
            "ops_station_events",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("station_id", sa.String(length=36), sa.ForeignKey(f"{DB_SCHEMA}.fuel_stations.id"), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("old_value", sa.String(length=64), nullable=True),
            sa.Column("new_value", sa.String(length=64), nullable=True),
            sa.Column("computed_metrics", sa.JSON(), nullable=True),
            sa.Column("policy_snapshot", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP") if bind.dialect.name == "sqlite" else sa.text("now()")),
            sa.Column("created_by", sa.String(length=128), nullable=False, server_default="system"),
            schema=DB_SCHEMA,
        )

    if not constraint_exists(bind, "ops_station_events", _EVENT_TYPE_CHECK, schema=DB_SCHEMA):
        op.create_check_constraint(
            _EVENT_TYPE_CHECK,
            "ops_station_events",
            "event_type IN ('HEALTH_CHANGED', 'RISK_CHANGED')",
            schema=DB_SCHEMA,
        )

    if not index_exists(bind, "ix_ops_station_events_station_created", schema=DB_SCHEMA):
        op.create_index(
            "ix_ops_station_events_station_created",
            "ops_station_events",
            ["station_id", "created_at"],
            unique=False,
            schema=DB_SCHEMA,
        )
    if not index_exists(bind, "ix_ops_station_events_type_created", schema=DB_SCHEMA):
        op.create_index(
            "ix_ops_station_events_type_created",
            "ops_station_events",
            ["event_type", "created_at"],
            unique=False,
            schema=DB_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, "ix_ops_station_events_type_created", schema=DB_SCHEMA):
        op.drop_index("ix_ops_station_events_type_created", table_name="ops_station_events", schema=DB_SCHEMA)
    if index_exists(bind, "ix_ops_station_events_station_created", schema=DB_SCHEMA):
        op.drop_index("ix_ops_station_events_station_created", table_name="ops_station_events", schema=DB_SCHEMA)
    if constraint_exists(bind, "ops_station_events", _EVENT_TYPE_CHECK, schema=DB_SCHEMA):
        op.drop_constraint(_EVENT_TYPE_CHECK, "ops_station_events", type_="check", schema=DB_SCHEMA)
    if table_exists(bind, "ops_station_events", schema=DB_SCHEMA):
        op.drop_table("ops_station_events", schema=DB_SCHEMA)

    if index_exists(bind, "ix_fuel_stations_risk_manual_lock", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_stations_risk_manual_lock", table_name="fuel_stations", schema=DB_SCHEMA)
    if index_exists(bind, "ix_fuel_stations_health_manual_lock", schema=DB_SCHEMA):
        op.drop_index("ix_fuel_stations_health_manual_lock", table_name="fuel_stations", schema=DB_SCHEMA)

    if constraint_exists(bind, "fuel_stations", _RISK_LOCK, schema=DB_SCHEMA):
        op.drop_constraint(_RISK_LOCK, "fuel_stations", type_="check", schema=DB_SCHEMA)
    if constraint_exists(bind, "fuel_stations", _HEALTH_LOCK, schema=DB_SCHEMA):
        op.drop_constraint(_HEALTH_LOCK, "fuel_stations", type_="check", schema=DB_SCHEMA)

    for name in ("risk_last_auto_at", "risk_manual_until", "health_last_auto_at", "health_manual_until"):
        if column_exists(bind, "fuel_stations", name, schema=DB_SCHEMA):
            op.drop_column("fuel_stations", name, schema=DB_SCHEMA)

    for name in ("risk_auto_enabled", "risk_manual_lock", "health_auto_enabled", "health_manual_lock"):
        if column_exists(bind, "fuel_stations", name, schema=DB_SCHEMA):
            op.drop_column("fuel_stations", name, schema=DB_SCHEMA)

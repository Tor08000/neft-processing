"""fuel domain v2 extensions

Revision ID: 20291320_0060_fuel_domain_v2
Revises: 20291301_0059_fuel_domain_v1
Create Date: 2029-02-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import column_exists, create_index_if_not_exists, ensure_pg_enum_value, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291320_0060_fuel_domain_v2"
down_revision = "20291301_0059_fuel_domain_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum_value(bind, "legal_node_type", "FUEL_LIMIT", schema=SCHEMA)

    if not table_exists(bind, "fuel_station_networks", schema=SCHEMA):
        op.create_table(
            "fuel_station_networks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            schema=SCHEMA,
        )

    if not column_exists(bind, "fuel_stations", "station_network_id", schema=SCHEMA):
        op.add_column(
            "fuel_stations",
            sa.Column("station_network_id", sa.String(36), nullable=True),
            schema=SCHEMA,
        )
        op.create_foreign_key(
            "fk_fuel_stations_station_network_id",
            "fuel_stations",
            "fuel_station_networks",
            ["station_network_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_stations_station_network_id",
            "fuel_stations",
            ["station_network_id"],
            schema=SCHEMA,
        )

    if not column_exists(bind, "fuel_limits", "fuel_type_code", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("fuel_type_code", sa.Enum(name="fuel_type"), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "fuel_limits", "station_id", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("station_id", sa.String(36), nullable=True),
            schema=SCHEMA,
        )
        op.create_foreign_key(
            "fk_fuel_limits_station_id",
            "fuel_limits",
            "fuel_stations",
            ["station_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_limits_station_id",
            "fuel_limits",
            ["station_id"],
            schema=SCHEMA,
        )
    if not column_exists(bind, "fuel_limits", "station_network_id", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("station_network_id", sa.String(36), nullable=True),
            schema=SCHEMA,
        )
        op.create_foreign_key(
            "fk_fuel_limits_station_network_id",
            "fuel_limits",
            "fuel_station_networks",
            ["station_network_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_limits_station_network_id",
            "fuel_limits",
            ["station_network_id"],
            schema=SCHEMA,
        )
    if not column_exists(bind, "fuel_limits", "time_window_start", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("time_window_start", sa.Time(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "fuel_limits", "time_window_end", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("time_window_end", sa.Time(), nullable=True),
            schema=SCHEMA,
        )
    if not column_exists(bind, "fuel_limits", "timezone", schema=SCHEMA):
        op.add_column(
            "fuel_limits",
            sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_risk_profiles", schema=SCHEMA):
        op.create_table(
            "fuel_risk_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("policy_id", sa.String(36), nullable=False),
            sa.Column("thresholds_override", sa.JSON, nullable=True),
            sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["policy_id"], [f"{SCHEMA}.risk_policies.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_risk_profiles_client_id",
            "fuel_risk_profiles",
            ["client_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_risk_shadow_events", schema=SCHEMA):
        op.create_table(
            "fuel_risk_shadow_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("fuel_tx_id", sa.String(36), nullable=False),
            sa.Column("decision", sa.String(32), nullable=False),
            sa.Column("score", sa.Integer, nullable=True),
            sa.Column("explain", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_risk_shadow_events_fuel_tx_id",
            "fuel_risk_shadow_events",
            ["fuel_tx_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_anomaly_events", schema=SCHEMA):
        op.create_table(
            "fuel_anomaly_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("fuel_tx_id", sa.String(36), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(32), nullable=False),
            sa.Column("explain", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_anomaly_events_fuel_tx_id",
            "fuel_anomaly_events",
            ["fuel_tx_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_misuse_signals", schema=SCHEMA):
        op.create_table(
            "fuel_misuse_signals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("fuel_tx_id", sa.String(36), nullable=False),
            sa.Column("signal", sa.String(64), nullable=False),
            sa.Column("explain", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_misuse_signals_fuel_tx_id",
            "fuel_misuse_signals",
            ["fuel_tx_id"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_station_outliers", schema=SCHEMA):
        op.create_table(
            "fuel_station_outliers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("station_id", sa.String(36), nullable=False),
            sa.Column("metric", sa.String(64), nullable=False),
            sa.Column("value", sa.BigInteger, nullable=True),
            sa.Column("baseline", sa.BigInteger, nullable=True),
            sa.Column("explain", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["station_id"], [f"{SCHEMA}.fuel_stations.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_station_outliers_station_id",
            "fuel_station_outliers",
            ["station_id"],
            schema=SCHEMA,
        )

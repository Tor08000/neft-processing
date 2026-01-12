"""fuel antifraud v3

Revision ID: 20291501_0069_fuel_antifraud_v3
Revises: 20291415_0068_merge_heads_0046_0067
Create Date: 2029-03-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, ensure_pg_enum, ensure_pg_enum_value, table_exists
from db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291501_0069_fuel_antifraud_v3"
down_revision = "20291415_0068_merge_heads_0046_0067"
branch_labels = None
depends_on = None

SIGNAL_TYPES = [
    "FUEL_OFF_ROUTE_STRONG",
    "FUEL_STOP_MISMATCH_STRONG",
    "MULTI_CARD_SAME_STATION_BURST",
    "REPEATED_NIGHT_REFUEL",
    "TANK_SANITY_REPEAT",
    "STATION_OUTLIER_CLUSTER",
    "DRIVER_VEHICLE_MISMATCH",
    "ROUTE_DEVIATION_BEFORE_FUEL",
]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fuel_fraud_signal_type", SIGNAL_TYPES, schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "FRAUD_SIGNAL", schema=SCHEMA)

    if not table_exists(bind, "fuel_fraud_signals", schema=SCHEMA):
        op.create_table(
            "fuel_fraud_signals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column(
                "signal_type",
                postgresql.ENUM(name="fuel_fraud_signal_type", schema=SCHEMA, create_type=False),
                nullable=False,
            ),
            sa.Column("severity", sa.Integer, nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fuel_tx_id", sa.String(36), nullable=True),
            sa.Column("order_id", sa.String(36), nullable=True),
            sa.Column("vehicle_id", sa.String(36), nullable=True),
            sa.Column("driver_id", sa.String(36), nullable=True),
            sa.Column("station_id", sa.String(36), nullable=True),
            sa.Column("network_id", sa.String(36), nullable=True),
            sa.Column("explain", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["fuel_tx_id"], [f"{SCHEMA}.fuel_transactions.id"]),
            sa.ForeignKeyConstraint(["order_id"], [f"{SCHEMA}.logistics_orders.id"]),
            sa.ForeignKeyConstraint(["vehicle_id"], [f"{SCHEMA}.fleet_vehicles.id"]),
            sa.ForeignKeyConstraint(["driver_id"], [f"{SCHEMA}.fleet_drivers.id"]),
            sa.ForeignKeyConstraint(["station_id"], [f"{SCHEMA}.fuel_stations.id"]),
            sa.ForeignKeyConstraint(["network_id"], [f"{SCHEMA}.fuel_networks.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_fraud_signals_client_ts",
            "fuel_fraud_signals",
            ["client_id", "ts"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_fraud_signals_vehicle_ts",
            "fuel_fraud_signals",
            ["vehicle_id", "ts"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_fraud_signals_station_ts",
            "fuel_fraud_signals",
            ["station_id", "ts"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_fuel_fraud_signals_signal_ts",
            "fuel_fraud_signals",
            ["signal_type", "ts"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "station_reputation_daily", schema=SCHEMA):
        op.create_table(
            "station_reputation_daily",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("network_id", sa.String(36), nullable=False),
            sa.Column("station_id", sa.String(36), nullable=False),
            sa.Column("day", sa.Date, nullable=False),
            sa.Column("tx_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("decline_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("risk_block_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("avg_liters", sa.Integer, nullable=True),
            sa.Column("avg_amount", sa.Integer, nullable=True),
            sa.Column("outlier_score", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["network_id"], [f"{SCHEMA}.fuel_networks.id"]),
            sa.ForeignKeyConstraint(["station_id"], [f"{SCHEMA}.fuel_stations.id"]),
            schema=SCHEMA,
        )
        create_index_if_not_exists(
            bind,
            "ix_station_reputation_daily_station_day",
            "station_reputation_daily",
            ["station_id", "day"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass

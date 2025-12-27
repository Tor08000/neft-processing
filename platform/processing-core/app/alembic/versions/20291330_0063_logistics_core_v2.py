"""logistics core v2 signals and links

Revision ID: 20291330_0063_logistics_core_v2
Revises: 20291325_0062_logistics_core_v1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import ensure_pg_enum, ensure_pg_enum_value, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291330_0063_logistics_core_v2"
down_revision = "20291325_0062_logistics_core_v1"
branch_labels = None
depends_on = None

LOGISTICS_DEVIATION_EVENT_TYPE = ["OFF_ROUTE", "BACK_ON_ROUTE", "STOP_OUT_OF_RADIUS", "UNEXPECTED_STOP"]
LOGISTICS_DEVIATION_SEVERITY = ["LOW", "MEDIUM", "HIGH"]
LOGISTICS_FUEL_LINK_TYPE = ["AUTO_MATCH", "MANUAL", "PROVIDER"]
LOGISTICS_RISK_SIGNAL_TYPE = [
    "FUEL_OFF_ROUTE",
    "FUEL_STOP_MISMATCH",
    "ROUTE_DEVIATION_HIGH",
    "ETA_ANOMALY",
    "VELOCITY_ANOMALY",
]
LOGISTICS_ETA_METHOD = ["PLANNED", "SIMPLE_SPEED", "LAST_KNOWN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "logistics_deviation_event_type", LOGISTICS_DEVIATION_EVENT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_deviation_severity", LOGISTICS_DEVIATION_SEVERITY, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_fuel_link_type", LOGISTICS_FUEL_LINK_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_risk_signal_type", LOGISTICS_RISK_SIGNAL_TYPE, schema=SCHEMA)

    ensure_pg_enum_value(bind, "legal_node_type", "LOGISTICS_DEVIATION_EVENT", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "LOGISTICS_RISK_SIGNAL", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "FUEL_ROUTE_LINK", schema=SCHEMA)

    if not table_exists(bind, "logistics_route_constraints", schema=SCHEMA):
        op.create_table(
            "logistics_route_constraints",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("route_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_routes.id"), nullable=False),
            sa.Column("max_route_deviation_m", sa.Integer, nullable=False),
            sa.Column("max_stop_radius_m", sa.Integer, nullable=False),
            sa.Column("allowed_fuel_window_minutes", sa.Integer, nullable=False),
            sa.Column("allowed_regions", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("route_id", name="uq_logistics_route_constraints_route_id"),
            schema=SCHEMA,
        )

    if not table_exists(bind, "logistics_deviation_events", schema=SCHEMA):
        op.create_table(
            "logistics_deviation_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("route_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_routes.id"), nullable=False),
            sa.Column(
                "event_type",
                sa.Enum(*LOGISTICS_DEVIATION_EVENT_TYPE, name="logistics_deviation_event_type"),
                nullable=False,
            ),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lat", sa.Float, nullable=True),
            sa.Column("lon", sa.Float, nullable=True),
            sa.Column("distance_from_route_m", sa.Integer, nullable=True),
            sa.Column("stop_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_stops.id"), nullable=True),
            sa.Column(
                "severity",
                sa.Enum(*LOGISTICS_DEVIATION_SEVERITY, name="logistics_deviation_severity"),
                nullable=False,
            ),
            sa.Column("explain", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_deviation_events_order_ts",
            "logistics_deviation_events",
            ["order_id", "ts"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "logistics_eta_accuracy", schema=SCHEMA):
        op.create_table(
            "logistics_eta_accuracy",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("eta_end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_minutes", sa.Integer, nullable=True),
            sa.Column("method", sa.Enum(*LOGISTICS_ETA_METHOD, name="logistics_eta_method"), nullable=False),
            sa.Column("confidence", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_eta_accuracy_order_ts",
            "logistics_eta_accuracy",
            ["order_id", "computed_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fuel_route_links", schema=SCHEMA):
        op.create_table(
            "fuel_route_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("fuel_tx_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_transactions.id"), nullable=False),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("route_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_routes.id"), nullable=True),
            sa.Column("stop_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_stops.id"), nullable=True),
            sa.Column("link_type", sa.Enum(*LOGISTICS_FUEL_LINK_TYPE, name="logistics_fuel_link_type"), nullable=False),
            sa.Column("distance_to_stop_m", sa.Integer, nullable=True),
            sa.Column("time_delta_minutes", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_fuel_route_links_order", "fuel_route_links", ["order_id"], schema=SCHEMA)

    if not table_exists(bind, "logistics_risk_signals", schema=SCHEMA):
        op.create_table(
            "logistics_risk_signals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("vehicle_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_vehicles.id"), nullable=True),
            sa.Column("driver_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_drivers.id"), nullable=True),
            sa.Column("signal_type", sa.Enum(*LOGISTICS_RISK_SIGNAL_TYPE, name="logistics_risk_signal_type"), nullable=False),
            sa.Column("severity", sa.Integer, nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("explain", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_risk_signals_order_ts",
            "logistics_risk_signals",
            ["order_id", "ts"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_index("ix_logistics_risk_signals_order_ts", table_name="logistics_risk_signals", schema=SCHEMA)
    op.drop_table("logistics_risk_signals", schema=SCHEMA)

    op.drop_index("ix_fuel_route_links_order", table_name="fuel_route_links", schema=SCHEMA)
    op.drop_table("fuel_route_links", schema=SCHEMA)

    op.drop_index("ix_logistics_eta_accuracy_order_ts", table_name="logistics_eta_accuracy", schema=SCHEMA)
    op.drop_table("logistics_eta_accuracy", schema=SCHEMA)

    op.drop_index("ix_logistics_deviation_events_order_ts", table_name="logistics_deviation_events", schema=SCHEMA)
    op.drop_table("logistics_deviation_events", schema=SCHEMA)

    op.drop_table("logistics_route_constraints", schema=SCHEMA)

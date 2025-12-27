"""logistics core v1

Revision ID: 20291325_0062_logistics_core_v1
Revises: 20291320_0061_fuel_hardening_v2
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import ensure_pg_enum, ensure_pg_enum_value, table_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291325_0062_logistics_core_v1"
down_revision = "20291320_0061_fuel_hardening_v2"
branch_labels = None
depends_on = None

LOGISTICS_ORDER_TYPE = ["DELIVERY", "SERVICE", "TRIP"]
LOGISTICS_ORDER_STATUS = ["DRAFT", "PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
LOGISTICS_ROUTE_STATUS = ["DRAFT", "ACTIVE", "ARCHIVED"]
LOGISTICS_STOP_TYPE = ["START", "WAYPOINT", "FUEL", "DELIVERY", "END"]
LOGISTICS_STOP_STATUS = ["PENDING", "ARRIVED", "DEPARTED", "SKIPPED"]
LOGISTICS_TRACKING_EVENT_TYPE = [
    "LOCATION",
    "STATUS_CHANGE",
    "STOP_ARRIVAL",
    "STOP_DEPARTURE",
    "FUEL_STOP_LINKED",
]
LOGISTICS_ETA_METHOD = ["PLANNED", "SIMPLE_SPEED", "LAST_KNOWN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "logistics_order_type", LOGISTICS_ORDER_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_order_status", LOGISTICS_ORDER_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_route_status", LOGISTICS_ROUTE_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_stop_type", LOGISTICS_STOP_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_stop_status", LOGISTICS_STOP_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_tracking_event_type", LOGISTICS_TRACKING_EVENT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "logistics_eta_method", LOGISTICS_ETA_METHOD, schema=SCHEMA)

    ensure_pg_enum_value(bind, "legal_node_type", "LOGISTICS_ORDER", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "LOGISTICS_ROUTE", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "LOGISTICS_STOP", schema=SCHEMA)
    ensure_pg_enum_value(bind, "legal_node_type", "DRIVER", schema=SCHEMA)

    if not table_exists(bind, "logistics_orders", schema=SCHEMA):
        op.create_table(
            "logistics_orders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.Integer, nullable=False),
            sa.Column("client_id", sa.String(64), nullable=False),
            sa.Column("order_type", sa.Enum(*LOGISTICS_ORDER_TYPE, name="logistics_order_type"), nullable=False),
            sa.Column("status", sa.Enum(*LOGISTICS_ORDER_STATUS, name="logistics_order_status"), nullable=False),
            sa.Column("vehicle_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_vehicles.id"), nullable=True),
            sa.Column("driver_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_drivers.id"), nullable=True),
            sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("origin_text", sa.String(256), nullable=True),
            sa.Column("destination_text", sa.String(256), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index("ix_logistics_orders_tenant_id", "logistics_orders", ["tenant_id"], schema=SCHEMA)
        op.create_index("ix_logistics_orders_client_id", "logistics_orders", ["client_id"], schema=SCHEMA)
        op.create_index(
            "ix_logistics_orders_client_status",
            "logistics_orders",
            ["client_id", "status"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_orders_vehicle_status",
            "logistics_orders",
            ["vehicle_id", "status"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_orders_driver_status",
            "logistics_orders",
            ["driver_id", "status"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_orders_planned_start_at",
            "logistics_orders",
            ["planned_start_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "logistics_routes", schema=SCHEMA):
        op.create_table(
            "logistics_routes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("status", sa.Enum(*LOGISTICS_ROUTE_STATUS, name="logistics_route_status"), nullable=False),
            sa.Column("distance_km", sa.Float, nullable=True),
            sa.Column("planned_duration_minutes", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id", "version", name="uq_logistics_routes_order_version"),
            schema=SCHEMA,
        )
        op.create_index("ix_logistics_routes_order_id", "logistics_routes", ["order_id"], schema=SCHEMA)

    if not table_exists(bind, "logistics_stops", schema=SCHEMA):
        op.create_table(
            "logistics_stops",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("route_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_routes.id"), nullable=False),
            sa.Column("sequence", sa.Integer, nullable=False),
            sa.Column("stop_type", sa.Enum(*LOGISTICS_STOP_TYPE, name="logistics_stop_type"), nullable=False),
            sa.Column("name", sa.String(128), nullable=True),
            sa.Column("address_text", sa.String(256), nullable=True),
            sa.Column("lat", sa.Float, nullable=True),
            sa.Column("lon", sa.Float, nullable=True),
            sa.Column("planned_arrival_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("planned_departure_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_arrival_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_departure_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.Enum(*LOGISTICS_STOP_STATUS, name="logistics_stop_status"), nullable=False),
            sa.Column("fuel_tx_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fuel_transactions.id"), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("route_id", "sequence", name="uq_logistics_stops_route_sequence"),
            schema=SCHEMA,
        )
        op.create_index("ix_logistics_stops_route_id", "logistics_stops", ["route_id"], schema=SCHEMA)
        op.create_index("ix_logistics_stops_status", "logistics_stops", ["status"], schema=SCHEMA)

    if not table_exists(bind, "logistics_tracking_events", schema=SCHEMA):
        op.create_table(
            "logistics_tracking_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("vehicle_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_vehicles.id"), nullable=True),
            sa.Column("driver_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.fleet_drivers.id"), nullable=True),
            sa.Column(
                "event_type",
                sa.Enum(*LOGISTICS_TRACKING_EVENT_TYPE, name="logistics_tracking_event_type"),
                nullable=False,
            ),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lat", sa.Float, nullable=True),
            sa.Column("lon", sa.Float, nullable=True),
            sa.Column("speed_kmh", sa.Float, nullable=True),
            sa.Column("heading_deg", sa.Float, nullable=True),
            sa.Column("odometer_km", sa.Float, nullable=True),
            sa.Column("stop_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_stops.id"), nullable=True),
            sa.Column("status_from", sa.String(32), nullable=True),
            sa.Column("status_to", sa.String(32), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_tracking_events_order_ts_desc",
            "logistics_tracking_events",
            ["order_id", sa.text("ts DESC")],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_tracking_events_vehicle_ts_desc",
            "logistics_tracking_events",
            ["vehicle_id", sa.text("ts DESC")],
            schema=SCHEMA,
        )

    if not table_exists(bind, "logistics_eta_snapshots", schema=SCHEMA):
        op.create_table(
            "logistics_eta_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.logistics_orders.id"), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("eta_end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("eta_confidence", sa.Integer, nullable=False),
            sa.Column("method", sa.Enum(*LOGISTICS_ETA_METHOD, name="logistics_eta_method"), nullable=False),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_logistics_eta_snapshots_order_computed_desc",
            "logistics_eta_snapshots",
            ["order_id", sa.text("computed_at DESC")],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_logistics_eta_snapshots_order_computed_desc",
        table_name="logistics_eta_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("logistics_eta_snapshots", schema=SCHEMA)

    op.drop_index(
        "ix_logistics_tracking_events_vehicle_ts_desc",
        table_name="logistics_tracking_events",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_logistics_tracking_events_order_ts_desc",
        table_name="logistics_tracking_events",
        schema=SCHEMA,
    )
    op.drop_table("logistics_tracking_events", schema=SCHEMA)

    op.drop_index("ix_logistics_stops_status", table_name="logistics_stops", schema=SCHEMA)
    op.drop_index("ix_logistics_stops_route_id", table_name="logistics_stops", schema=SCHEMA)
    op.drop_table("logistics_stops", schema=SCHEMA)

    op.drop_index("ix_logistics_routes_order_id", table_name="logistics_routes", schema=SCHEMA)
    op.drop_table("logistics_routes", schema=SCHEMA)

    op.drop_index("ix_logistics_orders_planned_start_at", table_name="logistics_orders", schema=SCHEMA)
    op.drop_index("ix_logistics_orders_driver_status", table_name="logistics_orders", schema=SCHEMA)
    op.drop_index("ix_logistics_orders_vehicle_status", table_name="logistics_orders", schema=SCHEMA)
    op.drop_index("ix_logistics_orders_client_status", table_name="logistics_orders", schema=SCHEMA)
    op.drop_index("ix_logistics_orders_client_id", table_name="logistics_orders", schema=SCHEMA)
    op.drop_index("ix_logistics_orders_tenant_id", table_name="logistics_orders", schema=SCHEMA)
    op.drop_table("logistics_orders", schema=SCHEMA)

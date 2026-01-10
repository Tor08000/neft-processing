"""vehicle profile v1 tables

Revision ID: 20295010_0112_vehicle_profile_v1
Revises: 20295000_0111_marketplace_gamification_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    table_exists,
)
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20295010_0112_vehicle_profile_v1"
down_revision = "20295000_0111_marketplace_gamification_v1"
branch_labels = None
depends_on = None

VEHICLE_ENGINE_TYPE = ["petrol", "diesel", "hybrid", "electric"]
VEHICLE_ODOMETER_SOURCE = ["MANUAL", "ESTIMATED", "MIXED"]
VEHICLE_USAGE_TYPE = ["city", "highway", "mixed", "aggressive"]
VEHICLE_MILEAGE_SOURCE = ["FUEL_TXN", "MANUAL_UPDATE", "SERVICE_EVENT"]
VEHICLE_RECOMMENDATION_STATUS = ["ACTIVE", "ACCEPTED", "DONE", "DISMISSED"]
VEHICLE_SERVICE_TYPE = ["OIL_CHANGE", "FILTERS", "BRAKES", "TIMING", "OTHER"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "vehicle_engine_type", VEHICLE_ENGINE_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "vehicle_odometer_source", VEHICLE_ODOMETER_SOURCE, schema=SCHEMA)
    ensure_pg_enum(bind, "vehicle_usage_type", VEHICLE_USAGE_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "vehicle_mileage_source", VEHICLE_MILEAGE_SOURCE, schema=SCHEMA)
    ensure_pg_enum(bind, "vehicle_recommendation_status", VEHICLE_RECOMMENDATION_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "vehicle_service_type", VEHICLE_SERVICE_TYPE, schema=SCHEMA)

    if not table_exists(bind, "vehicles", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicles",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column("client_id", sa.String(length=64), nullable=False),
                sa.Column("brand", sa.String(length=64), nullable=True),
                sa.Column("model", sa.String(length=64), nullable=True),
                sa.Column("year", sa.Integer(), nullable=True),
                sa.Column(
                    "engine_type",
                    sa.Enum(*VEHICLE_ENGINE_TYPE, name="vehicle_engine_type", native_enum=False),
                    nullable=True,
                ),
                sa.Column("engine_volume", sa.Numeric(), nullable=True),
                sa.Column("fuel_type", sa.String(length=32), nullable=True),
                sa.Column("vin", sa.String(length=64), nullable=True),
                sa.Column("plate_number", sa.String(length=32), nullable=True),
                sa.Column("start_odometer_km", sa.Numeric(), nullable=False),
                sa.Column("current_odometer_km", sa.Numeric(), nullable=False),
                sa.Column(
                    "odometer_source",
                    sa.Enum(*VEHICLE_ODOMETER_SOURCE, name="vehicle_odometer_source", native_enum=False),
                    nullable=False,
                ),
                sa.Column("avg_consumption_l_per_100km", sa.Numeric(), nullable=True),
                sa.Column(
                    "usage_type",
                    sa.Enum(*VEHICLE_USAGE_TYPE, name="vehicle_usage_type", native_enum=False),
                    nullable=True,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_unique_index_if_not_exists(
            bind,
            "uq_vehicle_plate_client",
            "vehicles",
            ["client_id", "plate_number"],
            schema=SCHEMA,
        )
        create_index_if_not_exists(bind, "ix_vehicles_client", "vehicles", ["client_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_vehicles_tenant", "vehicles", ["tenant_id"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_cards", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_cards",
            schema=SCHEMA,
            columns=(
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id")),
                sa.Column("card_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.fuel_cards.id")),
                sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("vehicle_id", "card_id", name="pk_vehicle_cards"),
            ),
        )
        create_index_if_not_exists(bind, "ix_vehicle_cards_vehicle", "vehicle_cards", ["vehicle_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_vehicle_cards_card", "vehicle_cards", ["card_id"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_mileage_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_mileage_events",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id"), nullable=False),
                sa.Column(
                    "source",
                    sa.Enum(*VEHICLE_MILEAGE_SOURCE, name="vehicle_mileage_source", native_enum=False),
                    nullable=False,
                ),
                sa.Column("fuel_txn_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.fuel_transactions.id")),
                sa.Column("liters", sa.Numeric(), nullable=True),
                sa.Column("estimated_km", sa.Numeric(), nullable=True),
                sa.Column("odometer_before", sa.Numeric(), nullable=False),
                sa.Column("odometer_after", sa.Numeric(), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_vehicle_mileage_events_vehicle", "vehicle_mileage_events", ["vehicle_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_vehicle_mileage_events_fuel_tx", "vehicle_mileage_events", ["fuel_txn_id"], schema=SCHEMA)

    if not table_exists(bind, "service_intervals", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "service_intervals",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("brand", sa.String(length=64), nullable=True),
                sa.Column("model", sa.String(length=64), nullable=True),
                sa.Column(
                    "engine_type",
                    sa.Enum(*VEHICLE_ENGINE_TYPE, name="vehicle_engine_type", native_enum=False),
                    nullable=True,
                ),
                sa.Column(
                    "service_type",
                    sa.Enum(*VEHICLE_SERVICE_TYPE, name="vehicle_service_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("interval_km", sa.Numeric(), nullable=False),
                sa.Column("interval_months", sa.Integer(), nullable=True),
                sa.Column("description", sa.String(length=256), nullable=True),
            ),
        )
        create_index_if_not_exists(bind, "ix_service_intervals_brand", "service_intervals", ["brand"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_intervals_model", "service_intervals", ["model"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_recommendations", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_recommendations",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey(f"{SCHEMA}.vehicles.id"), nullable=False),
                sa.Column(
                    "service_type",
                    sa.Enum(*VEHICLE_SERVICE_TYPE, name="vehicle_service_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("recommended_at_km", sa.Numeric(), nullable=False),
                sa.Column("current_km", sa.Numeric(), nullable=False),
                sa.Column(
                    "status",
                    sa.Enum(
                        *VEHICLE_RECOMMENDATION_STATUS,
                        name="vehicle_recommendation_status",
                        native_enum=False,
                    ),
                    nullable=False,
                ),
                sa.Column("reason", sa.String(length=512), nullable=False),
                sa.Column("partner_id", sa.String(length=64), sa.ForeignKey(f"{SCHEMA}.partners.id"), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(
            bind,
            "ix_vehicle_recommendations_vehicle",
            "vehicle_recommendations",
            ["vehicle_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass

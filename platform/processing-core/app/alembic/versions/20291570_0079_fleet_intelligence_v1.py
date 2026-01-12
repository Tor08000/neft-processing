"""fleet intelligence v1 tables

Revision ID: 20291570_0079_fleet_intelligence_v1
Revises: 20291560_0078_ops_reason_codes
Create Date: 2029-05-70 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_table_if_not_exists, ensure_pg_enum, table_exists
from db.schema import resolve_db_schema


SCHEMA = resolve_db_schema().schema

revision = "20291570_0079_fleet_intelligence_v1"
down_revision = "20291560_0078_ops_reason_codes"
branch_labels = None
depends_on = None

DRIVER_BEHAVIOR_LEVEL = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
STATION_TRUST_LEVEL = ["TRUSTED", "WATCHLIST", "BLACKLIST"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "fi_driver_behavior_level", DRIVER_BEHAVIOR_LEVEL, schema=SCHEMA)
    ensure_pg_enum(bind, "fi_station_trust_level", STATION_TRUST_LEVEL, schema=SCHEMA)

    if not table_exists(bind, "fi_driver_daily", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_driver_daily",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column("driver_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("day", sa.Date, nullable=False),
                sa.Column("fuel_tx_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("fuel_volume_ml", sa.BigInteger, nullable=False, server_default="0"),
                sa.Column("fuel_amount_minor", sa.BigInteger, nullable=False, server_default="0"),
                sa.Column("night_fuel_tx_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("off_route_fuel_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("route_deviation_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("review_required_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("risk_block_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint(
                    "tenant_id",
                    "driver_id",
                    "day",
                    name="uq_fi_driver_daily_tenant_driver_day",
                ),
            ),
        )
        op.create_index(
            "ix_fi_driver_daily_tenant_driver_day",
            "fi_driver_daily",
            ["tenant_id", "driver_id", "day"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fi_vehicle_daily", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_vehicle_daily",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column("vehicle_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("day", sa.Date, nullable=False),
                sa.Column("fuel_volume_ml", sa.BigInteger, nullable=False, server_default="0"),
                sa.Column("fuel_amount_minor", sa.BigInteger, nullable=False, server_default="0"),
                sa.Column("distance_km_estimate", sa.Float, nullable=True),
                sa.Column("fuel_per_100km_ml", sa.Float, nullable=True),
                sa.Column("off_route_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("tank_sanity_exceeded_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint(
                    "tenant_id",
                    "vehicle_id",
                    "day",
                    name="uq_fi_vehicle_daily_tenant_vehicle_day",
                ),
            ),
        )
        op.create_index(
            "ix_fi_vehicle_daily_tenant_vehicle_day",
            "fi_vehicle_daily",
            ["tenant_id", "vehicle_id", "day"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fi_station_daily", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_station_daily",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("network_id", postgresql.UUID(as_uuid=False), nullable=True),
                sa.Column("station_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("day", sa.Date, nullable=False),
                sa.Column("tx_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("distinct_cards_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("distinct_drivers_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("avg_volume_ml", sa.BigInteger, nullable=True),
                sa.Column("avg_amount_minor", sa.BigInteger, nullable=True),
                sa.Column("risk_block_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("decline_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("burst_events_count", sa.Integer, nullable=False, server_default="0"),
                sa.Column("outlier_score", sa.Integer, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint(
                    "tenant_id",
                    "station_id",
                    "day",
                    name="uq_fi_station_daily_tenant_station_day",
                ),
            ),
        )
        op.create_index(
            "ix_fi_station_daily_tenant_station_day",
            "fi_station_daily",
            ["tenant_id", "station_id", "day"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fi_driver_score", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_driver_score",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column("driver_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column("score", sa.Integer, nullable=False),
                sa.Column(
                    "level",
                    postgresql.ENUM(
                        *DRIVER_BEHAVIOR_LEVEL,
                        name="fi_driver_behavior_level",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("explain", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_fi_driver_score_driver_window",
            "fi_driver_score",
            ["driver_id", "window_days", "computed_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fi_vehicle_efficiency_score", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_vehicle_efficiency_score",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("client_id", sa.String(64), nullable=False),
                sa.Column("vehicle_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column("efficiency_score", sa.Integer, nullable=True),
                sa.Column("baseline_ml_per_100km", sa.Float, nullable=True),
                sa.Column("actual_ml_per_100km", sa.Float, nullable=True),
                sa.Column("delta_pct", sa.Float, nullable=True),
                sa.Column("explain", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_fi_vehicle_score_vehicle_window",
            "fi_vehicle_efficiency_score",
            ["vehicle_id", "window_days", "computed_at"],
            schema=SCHEMA,
        )

    if not table_exists(bind, "fi_station_trust_score", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "fi_station_trust_score",
            schema=SCHEMA,
            columns=(
                sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
                sa.Column("tenant_id", sa.Integer, nullable=False),
                sa.Column("station_id", postgresql.UUID(as_uuid=False), nullable=False),
                sa.Column("network_id", postgresql.UUID(as_uuid=False), nullable=True),
                sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("window_days", sa.Integer, nullable=False),
                sa.Column("trust_score", sa.Integer, nullable=False),
                sa.Column(
                    "level",
                    postgresql.ENUM(
                        *STATION_TRUST_LEVEL,
                        name="fi_station_trust_level",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=False,
                ),
                sa.Column("explain", sa.JSON, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.PrimaryKeyConstraint("id"),
            ),
        )
        op.create_index(
            "ix_fi_station_score_station_window",
            "fi_station_trust_score",
            ["station_id", "window_days", "computed_at"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    pass

"""add risk zone fields to fuel stations

Revision ID: 20299640_0173_fuel_station_risk_zone
Revises: 20299630_0172_operation_station_fk
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, index_exists


revision = "20299640_0173_fuel_station_risk_zone"
down_revision = "20299630_0172_operation_station_fk"
branch_labels = None
depends_on = None

_ALLOWED_RISK_ZONES = ("GREEN", "YELLOW", "RED")
_CHECK_NAME = "ck_fuel_stations_risk_zone_allowed"
_INDEX_NAME = "ix_fuel_stations_risk_zone"


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "fuel_stations", "risk_zone", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("risk_zone", sa.String(length=16), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "risk_zone_reason", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("risk_zone_reason", sa.Text(), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "risk_zone_updated_at", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("risk_zone_updated_at", sa.DateTime(timezone=True), nullable=True), schema=DB_SCHEMA)
    if not column_exists(bind, "fuel_stations", "risk_zone_updated_by", schema=DB_SCHEMA):
        op.add_column("fuel_stations", sa.Column("risk_zone_updated_by", sa.String(length=256), nullable=True), schema=DB_SCHEMA)

    op.create_check_constraint(
        _CHECK_NAME,
        "fuel_stations",
        f"risk_zone IS NULL OR risk_zone IN {str(_ALLOWED_RISK_ZONES)}",
        schema=DB_SCHEMA,
    )

    if not index_exists(bind, _INDEX_NAME, schema=DB_SCHEMA):
        op.create_index(_INDEX_NAME, "fuel_stations", ["risk_zone"], unique=False, schema=DB_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, _INDEX_NAME, schema=DB_SCHEMA):
        op.drop_index(_INDEX_NAME, table_name="fuel_stations", schema=DB_SCHEMA)

    op.drop_constraint(_CHECK_NAME, "fuel_stations", type_="check", schema=DB_SCHEMA)

    if column_exists(bind, "fuel_stations", "risk_zone_updated_by", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "risk_zone_updated_by", schema=DB_SCHEMA)
    if column_exists(bind, "fuel_stations", "risk_zone_updated_at", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "risk_zone_updated_at", schema=DB_SCHEMA)
    if column_exists(bind, "fuel_stations", "risk_zone_reason", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "risk_zone_reason", schema=DB_SCHEMA)
    if column_exists(bind, "fuel_stations", "risk_zone", schema=DB_SCHEMA):
        op.drop_column("fuel_stations", "risk_zone", schema=DB_SCHEMA)

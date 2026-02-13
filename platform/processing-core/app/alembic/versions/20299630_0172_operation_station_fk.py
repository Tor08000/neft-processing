"""add fuel_station_id to operations

Revision ID: 20299630_0172_operation_station_fk
Revises: 20299620_0171_add_geo_fields_to_stations
Create Date: 2026-02-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, index_exists


revision = "20299630_0172_operation_station_fk"
down_revision = "20299620_0171_add_geo_fields_to_stations"
branch_labels = None
depends_on = None



def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "operations", "fuel_station_id", schema=DB_SCHEMA):
        op.add_column("operations", sa.Column("fuel_station_id", sa.String(length=36), nullable=True), schema=DB_SCHEMA)

    if not index_exists(bind, "ix_operations_fuel_station_id", schema=DB_SCHEMA):
        op.create_index("ix_operations_fuel_station_id", "operations", ["fuel_station_id"], unique=False, schema=DB_SCHEMA)

    fk_name = "fk_operations_fuel_station_id"
    inspector = sa.inspect(bind)
    existing_fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("operations", schema=DB_SCHEMA) if fk.get("name")}
    if fk_name not in existing_fk_names:
        op.create_foreign_key(
            fk_name,
            "operations",
            "fuel_stations",
            ["fuel_station_id"],
            ["id"],
            source_schema=DB_SCHEMA,
            referent_schema=DB_SCHEMA,
            ondelete="SET NULL",
        )



def downgrade() -> None:
    bind = op.get_bind()
    fk_name = "fk_operations_fuel_station_id"
    inspector = sa.inspect(bind)
    existing_fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("operations", schema=DB_SCHEMA) if fk.get("name")}

    if fk_name in existing_fk_names:
        op.drop_constraint(fk_name, "operations", type_="foreignkey", schema=DB_SCHEMA)

    if index_exists(bind, "ix_operations_fuel_station_id", schema=DB_SCHEMA):
        op.drop_index("ix_operations_fuel_station_id", table_name="operations", schema=DB_SCHEMA)

    if column_exists(bind, "operations", "fuel_station_id", schema=DB_SCHEMA):
        op.drop_column("operations", "fuel_station_id", schema=DB_SCHEMA)

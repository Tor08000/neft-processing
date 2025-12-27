"""logistics fuel link idempotency

Revision ID: 20291335_0064_logistics_fuel_link_unique
Revises: 20291330_0063_logistics_core_v2
"""

from __future__ import annotations

from alembic import op

from app.alembic.utils import constraint_exists
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20291335_0064_logistics_fuel_link_unique"
down_revision = "20291330_0063_logistics_core_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not constraint_exists(
        op.get_bind(),
        "fuel_route_links",
        "uq_fuel_route_links_fuel_tx_id",
        schema=SCHEMA,
    ):
        op.create_unique_constraint(
            "uq_fuel_route_links_fuel_tx_id",
            "fuel_route_links",
            ["fuel_tx_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_constraint(
        "uq_fuel_route_links_fuel_tx_id",
        "fuel_route_links",
        schema=SCHEMA,
        type_="unique",
    )

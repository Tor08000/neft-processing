"""crm feature flag subscription meter fuel

Revision ID: 20291430_0073_crm_feature_flag_subscription_meter_fuel
Revises: 20291420_0072_money_flow_link_node_types
Create Date: 2029-04-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import SCHEMA, ensure_pg_enum_value, is_postgres

revision = "20291430_0073_crm_feature_flag_subscription_meter_fuel"
down_revision = "20291420_0072_money_flow_link_node_types"
branch_labels = None
depends_on = None

NEW_FEATURE_FLAGS = ["SUBSCRIPTION_METER_FUEL_ENABLED"]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    for value in NEW_FEATURE_FLAGS:
        ensure_pg_enum_value(bind, "crm_feature_flag", value, schema=SCHEMA)


def downgrade() -> None:
    pass

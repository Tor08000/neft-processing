"""money flow link node types

Revision ID: 20291420_0072_money_flow_link_node_types
Revises: 20291420_0071_subscriptions_v2_segments_and_rules
Create Date: 2029-04-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from app.alembic.utils import SCHEMA, ensure_pg_enum_value, is_postgres

revision = "20291420_0072_money_flow_link_node_types"
down_revision = "20291420_0071_subscriptions_v2_segments_and_rules"
branch_labels = None
depends_on = None

NEW_NODE_TYPES = [
    "SUBSCRIPTION_SEGMENT",
    "USAGE_COUNTER",
    "DOCUMENT",
]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    for value in NEW_NODE_TYPES:
        ensure_pg_enum_value(bind, "money_flow_link_node_type", value, schema=SCHEMA)


def downgrade() -> None:
    pass

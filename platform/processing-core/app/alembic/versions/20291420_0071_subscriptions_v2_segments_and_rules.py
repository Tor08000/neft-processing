"""subscriptions v2 segments and rules

Revision ID: 20291420_0071_subscriptions_v2_segments_and_rules
Revises: 20291510_0070_money_flow_v2
Create Date: 2029-04-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import SCHEMA, column_exists, constraint_exists, ensure_pg_enum, is_postgres, table_exists

revision = "20291420_0071_subscriptions_v2_segments_and_rules"
down_revision = "20291510_0070_money_flow_v2"
branch_labels = None
depends_on = None


CRM_SUBSCRIPTION_SEGMENT_REASON = ["START", "UPGRADE", "DOWNGRADE", "PAUSE", "RESUME", "CANCEL"]
SEGMENT_ID_LEN = 36


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum(bind, "crm_subscription_segment_reason", CRM_SUBSCRIPTION_SEGMENT_REASON, schema=SCHEMA)

    if table_exists(bind, "crm_subscription_period_segments", schema=SCHEMA):
        if not column_exists(bind, "crm_subscription_period_segments", "reason", schema=SCHEMA):
            op.add_column(
                "crm_subscription_period_segments",
                sa.Column(
                    "reason",
                    postgresql.ENUM(
                        *CRM_SUBSCRIPTION_SEGMENT_REASON,
                        name="crm_subscription_segment_reason",
                        schema=SCHEMA,
                        create_type=False,
                    ),
                    nullable=True,
                ),
                schema=SCHEMA,
            )
        if constraint_exists(bind, "crm_subscription_period_segments", "uq_crm_subscription_segment_period", schema=SCHEMA):
            op.drop_constraint(
                "uq_crm_subscription_segment_period",
                "crm_subscription_period_segments",
                type_="unique",
                schema=SCHEMA,
            )
        op.create_unique_constraint(
            "uq_crm_subscription_segment_period",
            "crm_subscription_period_segments",
            ["subscription_id", "billing_period_id", "segment_start", "segment_end", "tariff_plan_id", "status"],
            schema=SCHEMA,
        )

    if table_exists(bind, "crm_usage_counters", schema=SCHEMA):
        if not column_exists(bind, "crm_usage_counters", "segment_id", schema=SCHEMA):
            op.add_column(
                "crm_usage_counters",
                sa.Column("segment_id", sa.String(SEGMENT_ID_LEN), nullable=True),
                schema=SCHEMA,
            )
        if not constraint_exists(bind, "crm_usage_counters", "fk_crm_usage_counters_segment", schema=SCHEMA):
            op.create_foreign_key(
                "fk_crm_usage_counters_segment",
                "crm_usage_counters",
                "crm_subscription_period_segments",
                ["segment_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )

    if table_exists(bind, "crm_subscription_charges", schema=SCHEMA):
        if not column_exists(bind, "crm_subscription_charges", "segment_id", schema=SCHEMA):
            op.add_column(
                "crm_subscription_charges",
                sa.Column("segment_id", sa.String(SEGMENT_ID_LEN), nullable=True),
                schema=SCHEMA,
            )
        if not constraint_exists(bind, "crm_subscription_charges", "fk_crm_subscription_charges_segment", schema=SCHEMA):
            op.create_foreign_key(
                "fk_crm_subscription_charges_segment",
                "crm_subscription_charges",
                "crm_subscription_period_segments",
                ["segment_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not column_exists(bind, "crm_subscription_charges", "charge_key", schema=SCHEMA):
            op.add_column(
                "crm_subscription_charges",
                sa.Column("charge_key", sa.String(128), nullable=True),
                schema=SCHEMA,
            )
        if not column_exists(bind, "crm_subscription_charges", "explain", schema=SCHEMA):
            op.add_column("crm_subscription_charges", sa.Column("explain", sa.JSON, nullable=True), schema=SCHEMA)
        if not constraint_exists(bind, "crm_subscription_charges", "uq_crm_subscription_charge_key", schema=SCHEMA):
            op.create_unique_constraint(
                "uq_crm_subscription_charge_key",
                "crm_subscription_charges",
                ["subscription_id", "billing_period_id", "charge_key"],
                schema=SCHEMA,
            )


def downgrade() -> None:
    pass

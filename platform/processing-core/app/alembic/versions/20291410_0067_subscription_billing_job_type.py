"""Add subscription billing job type and segments

Revision ID: 20291410_0067_subscription_billing_job_type
Revises: 20291405_0066_crm_subscriptions_v1
Create Date: 2029-14-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import SCHEMA, ensure_pg_enum, ensure_pg_enum_value, is_postgres, table_exists

# revision identifiers, used by Alembic.
revision = "20291410_0067_subscription_billing_job_type"
down_revision = "20291405_0066_crm_subscriptions_v1"
branch_labels = None
depends_on = None


CRM_SUBSCRIPTION_SEGMENT_STATUS = ["ACTIVE", "PAUSED"]


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum_value(bind, "billing_job_type", "SUBSCRIPTION_BILLING", schema=SCHEMA)
    ensure_pg_enum(bind, "crm_subscription_segment_status", CRM_SUBSCRIPTION_SEGMENT_STATUS, schema=SCHEMA)

    if not table_exists(bind, "crm_subscription_period_segments", schema=SCHEMA):
        op.create_table(
            "crm_subscription_period_segments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("subscription_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.crm_subscriptions.id"), nullable=False),
            sa.Column("billing_period_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.billing_periods.id"), nullable=False),
            sa.Column("tariff_plan_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.crm_tariff_plans.id"), nullable=False),
            sa.Column("segment_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("segment_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "status",
                postgresql.ENUM(
                    *CRM_SUBSCRIPTION_SEGMENT_STATUS,
                    name="crm_subscription_segment_status",
                    schema=SCHEMA,
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("days_count", sa.Integer, nullable=False),
            sa.Column("meta", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.UniqueConstraint(
                "subscription_id",
                "billing_period_id",
                "segment_start",
                "segment_end",
                name="uq_crm_subscription_segment_period",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_crm_subscription_segments_period",
            "crm_subscription_period_segments",
            ["subscription_id", "billing_period_id"],
            schema=SCHEMA,
        )


def downgrade():
    # Enum value removal is intentionally skipped to keep migrations idempotent
    pass

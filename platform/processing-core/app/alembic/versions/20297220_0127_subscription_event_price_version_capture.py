"""Add price version capture event type.

Revision ID: 20297220_0127_subscription_event_price_version_capture
Revises: 20297210_0126_pricing_versions_v1
Create Date: 2029-09-11 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from app.alembic.utils import SCHEMA, ensure_pg_enum_value


revision = "20297220_0127_subscription_event_price_version_capture"
down_revision = "20297210_0126_pricing_versions_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum_value(bind, "subscription_event_type", "PRICE_VERSION_CAPTURED", schema=SCHEMA)


def downgrade() -> None:
    pass

"""external request logs table

Revision ID: 20270101_0019_external_request_logs
Revises: 20261205_0018_contract_limits
Create Date: 2027-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_index_if_exists,
    drop_table_if_exists,
    table_exists,
)


# revision identifiers, used by Alembic.
revision = "20270101_0019_external_request_logs"
down_revision = "20261205_0018_contract_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_not_exists(
        bind,
        "external_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("partner_id", sa.String(length=64), nullable=False),
        sa.Column("azs_id", sa.String(length=64), nullable=True),
        sa.Column("terminal_id", sa.String(length=64), nullable=True),
        sa.Column("operation_id", sa.String(length=128), nullable=True),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("liters", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_category", sa.String(length=32), nullable=True),
        sa.Column("risk_code", sa.String(length=64), nullable=True),
        sa.Column("limit_code", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    create_index_if_not_exists(
        bind, "ix_external_request_logs_partner", "external_request_logs", ["partner_id"]
    )
    create_index_if_not_exists(
        bind, "ix_external_request_logs_azs", "external_request_logs", ["azs_id"]
    )
    create_index_if_not_exists(
        bind, "ix_external_request_logs_status", "external_request_logs", ["status"]
    )
    create_index_if_not_exists(
        bind, "ix_external_request_logs_created", "external_request_logs", ["created_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()

    if table_exists(bind, "external_request_logs"):
        drop_index_if_exists(bind, "ix_external_request_logs_created")
        drop_index_if_exists(bind, "ix_external_request_logs_status")
        drop_index_if_exists(bind, "ix_external_request_logs_azs")
        drop_index_if_exists(bind, "ix_external_request_logs_partner")
        drop_table_if_exists(bind, "external_request_logs")

"""external request logs table

Revision ID: 20270101_0019
Revises: 20261205_0018_contract_limits
Create Date: 2027-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20270101_0019"
down_revision = "20261205_0018_contract_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
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
    op.create_index("ix_external_request_logs_partner", "external_request_logs", ["partner_id"])
    op.create_index("ix_external_request_logs_azs", "external_request_logs", ["azs_id"])
    op.create_index("ix_external_request_logs_status", "external_request_logs", ["status"])
    op.create_index("ix_external_request_logs_created", "external_request_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_external_request_logs_created", table_name="external_request_logs")
    op.drop_index("ix_external_request_logs_status", table_name="external_request_logs")
    op.drop_index("ix_external_request_logs_azs", table_name="external_request_logs")
    op.drop_index("ix_external_request_logs_partner", table_name="external_request_logs")
    op.drop_table("external_request_logs")

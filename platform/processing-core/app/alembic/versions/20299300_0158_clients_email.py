"""Add email to clients.

Revision ID: 20299300_0158_clients_email
Revises: 20299290_0157_partner_payout_correlation_id
Create Date: 2026-04-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA


revision = "20299300_0158_clients_email"
down_revision = "20299290_0157_partner_payout_correlation_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("email", sa.Text(), nullable=True), schema=DB_SCHEMA)


def downgrade() -> None:
    op.drop_column("clients", "email", schema=DB_SCHEMA)

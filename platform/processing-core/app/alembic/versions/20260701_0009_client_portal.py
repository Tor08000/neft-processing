"""restore client portal revision as no-op migration

Revision ID: 20260701_0009_client_portal
Revises: 20260110_0009_create_clearing_table
Create Date: 2026-07-01 00:09:00
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260701_0009_client_portal"
down_revision = "20260110_0009_create_clearing_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op migration to preserve historical revision references."""


def downgrade() -> None:
    """No-op migration to preserve historical revision references."""

"""Merge multiple heads into single branch.

Revision ID: 20270215_0021_merge_heads
Revises: 20260110_0009_create_clearing_table, 20260701_0009_client_portal, 20270115_0020, 20270201_0020
Create Date: 2027-02-15 00:00:00
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20270215_0021_merge_heads"
down_revision = (
    "20260110_0009_create_clearing_table",
    "20260701_0009_client_portal",
    "20270115_0020",
    "20270201_0020",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op merge migration."""
    pass


def downgrade() -> None:
    """No-op merge migration."""
    pass

"""Alias for operations limits alignment revision id update

Revision ID: 20261020_0013_operations_limits_alignment
Revises: 20261020_0013
Create Date: 2026-10-20 00:00:01.000000
"""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20261020_0013_operations_limits_alignment"
down_revision = "20261020_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alias revision only; no DB changes.
    return


def downgrade() -> None:
    return

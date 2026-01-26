"""Merge auth_vernum + user_clients heads.

Revision ID: 20251010_0002_merge_auth_vernum_user_clients
Revises: 20251003_0002_auth_vernum, 20251010_0001_user_clients
Create Date: 2025-10-10 00:02:00.000000
"""

from __future__ import annotations


# revision identifiers, used by Alembic.
revision = "20251010_0002_merge_auth_vernum_user_clients"
down_revision = ("20251003_0002_auth_vernum", "20251010_0001_user_clients")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge-only revision."""


def downgrade() -> None:
    """Merge-only revision."""

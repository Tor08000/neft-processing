"""Ensure alembic_version_core.version_num fits long revisions early

Revision ID: 20251121_0003a_extend_alembic_version_len
Revises: 20251120_0003_limits_rules_v2
Create Date: 2025-11-21 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

from alembic_helpers import ensure_alembic_version_length


# revision identifiers, used by Alembic.
revision = "20251121_0003a_extend_alembic_version_len"
down_revision = "20251120_0003_limits_rules_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend version_num before migrations with long revision ids.

    Earlier databases were created with ``VARCHAR(32)`` for ``alembic_version_core.version_num``.
    Revisions like ``20251124_0003_merchants_terminals_cards`` exceed that length, so we
    enlarge the column before those migrations run to avoid StringDataRightTruncation.
    """

    ensure_alembic_version_length(op.get_bind(), min_length=128)


def downgrade() -> None:
    # Avoid shrinking the column to prevent truncating longer revision ids that may already be stored.
    pass

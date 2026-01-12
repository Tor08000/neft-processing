"""Extend alembic_version_core.version_num length

Revision ID: 20270301_0022_extend_alembic_version_len
Revises: 20270215_0021_merge_heads
Create Date: 2027-03-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from alembic_helpers import ensure_alembic_version_length


# revision identifiers, used by Alembic.
revision = "20270301_0022_extend_alembic_version_len"
down_revision = "20270215_0021_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    ensure_alembic_version_length(connection)


def downgrade() -> None:
    # Downgrade is intentionally a no-op to avoid truncating long revision ids.
    pass

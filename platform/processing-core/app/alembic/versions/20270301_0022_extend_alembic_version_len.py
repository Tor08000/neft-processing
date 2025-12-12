"""Extend alembic_version.version_num length

Revision ID: 20270301_0022_extend_alembic_version_len
Revises: 20270215_0021_merge_heads
Create Date: 2027-03-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20270301_0022_extend_alembic_version_len"
down_revision = "20270215_0021_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
    )


def downgrade() -> None:
    # Downgrade is intentionally a no-op to avoid truncating long revision ids.
    pass

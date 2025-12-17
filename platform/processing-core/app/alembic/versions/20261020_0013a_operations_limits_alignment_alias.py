"""Alias for operations limits alignment revision id update

Revision ID: 20261020_0013_operations_limits_alignment
Revises: 20261020_0013
Create Date: 2026-10-20 00:00:01.000000
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261020_0013_operations_limits_alignment"
down_revision = "20261020_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alias migration to map the previous revision id to the new one without DB changes.
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    bind.exec_driver_sql(
        """
        UPDATE alembic_version
        SET version_num = '20261020_0013_operations_limits_alignment'
        WHERE version_num = '20261020_0013'
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    bind.exec_driver_sql(
        """
        UPDATE alembic_version
        SET version_num = '20261020_0013'
        WHERE version_num = '20261020_0013_operations_limits_alignment'
        """
    )

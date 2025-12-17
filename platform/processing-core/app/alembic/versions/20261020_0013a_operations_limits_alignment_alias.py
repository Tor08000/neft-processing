"""Alias for operations limits alignment revision id update

Revision ID: 20261020_0013_operations_limits_alignment
Revises: 20261020_0013
Create Date: 2026-10-20 00:00:01.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


def _get_current_alembic_version(bind: sa.engine.Connection) -> str | None:
    table_exists = bind.exec_driver_sql("SELECT to_regclass('public.alembic_version')").scalar()
    if not table_exists:
        return None

    return bind.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()


def _update_if_matches(bind: sa.engine.Connection, expected: str, new: str) -> None:
    if _get_current_alembic_version(bind) != expected:
        return

    bind.exec_driver_sql(
        """
        UPDATE alembic_version
        SET version_num = %(new)s
        WHERE version_num = %(expected)s
        """,
        {"new": new, "expected": expected},
    )

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

    _update_if_matches(bind, "20261020_0013", "20261020_0013_operations_limits_alignment")


def downgrade() -> None:
    bind = op.get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    _update_if_matches(bind, "20261020_0013_operations_limits_alignment", "20261020_0013")

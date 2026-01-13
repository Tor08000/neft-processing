"""Expand auth alembic version column length.

Revision ID: 20251003_0002_auth_vernum
Revises: 20251003_0001_bootstrap_pwd_ver
Create Date: 2025-10-03 00:02:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_0002_auth_vernum"
down_revision = "20251003_0001_bootstrap_pwd_ver"
branch_labels = None
depends_on = None


AUTH_SCHEMA = "public"
VERSION_TABLE = "alembic_version_auth"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {AUTH_SCHEMA}.{VERSION_TABLE}
            ALTER COLUMN version_num TYPE varchar(128);
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {AUTH_SCHEMA}.{VERSION_TABLE}
            ALTER COLUMN version_num TYPE varchar(32);
            """
        )
    )

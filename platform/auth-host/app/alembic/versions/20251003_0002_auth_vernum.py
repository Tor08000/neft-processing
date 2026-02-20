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


def _alter_version_num_if_table_exists(column_type: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF to_regclass('{AUTH_SCHEMA}.{VERSION_TABLE}') IS NOT NULL THEN
                ALTER TABLE {AUTH_SCHEMA}.{VERSION_TABLE}
                  ALTER COLUMN version_num TYPE {column_type};
              END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _alter_version_num_if_table_exists("varchar(128)")


def downgrade() -> None:
    _alter_version_num_if_table_exists("varchar(32)")

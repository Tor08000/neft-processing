"""Ensure deterministic default tenant for bootstrap users.

Revision ID: 20251027_0001_default_tenant_neft
Revises: 20251026_0001_users_email_unique_for_bootstrap
Create Date: 2025-10-27 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251027_0001_default_tenant_neft"
down_revision = "20251026_0001_users_email_unique_for_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO public.tenants (code, name)
            VALUES ('neft', 'NEFT Platform')
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            """
        )
    )


def downgrade() -> None:
    # Keep tenant row intact to avoid orphaning users in environments
    # where bootstrap accounts have already been assigned to it.
    return

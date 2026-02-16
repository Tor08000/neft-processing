"""Add invitation search/support indexes.

Revision ID: 20299920_0195_client_invitation_indexes
Revises: 20299910_0194_client_invitation_resend_revoke_notifications
Create Date: 2026-02-18 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from alembic_helpers import DB_SCHEMA

revision = "20299920_0195_client_invitation_indexes"
down_revision = "20299910_0194_client_invitation_resend_revoke_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_client_invitations_email_lower ON {DB_SCHEMA}.client_invitations (lower(email))"))
    op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_client_invitations_expires_at ON {DB_SCHEMA}.client_invitations (expires_at)"))


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {DB_SCHEMA}.ix_client_invitations_expires_at"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {DB_SCHEMA}.ix_client_invitations_email_lower"))

"""Allow onboarding OTP challenges without a mounted client_id.

Revision ID: 20300250_0218_otp_challenges_nullable_client_id
Revises: 20300240_0217_notification_outbox_shape_runtime_repair
Create Date: 2030-01-19 02:50:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import DB_SCHEMA, column_exists, table_exists


revision = "20300250_0218_otp_challenges_nullable_client_id"
down_revision = "20300240_0217_notification_outbox_shape_runtime_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "otp_challenges", schema=DB_SCHEMA):
        return
    if not column_exists(bind, "otp_challenges", "client_id", schema=DB_SCHEMA):
        return

    op.alter_column("otp_challenges", "client_id", nullable=True, schema=DB_SCHEMA)


def downgrade() -> None:
    # Keep relaxation additive-only; onboarding-generated docs may legitimately
    # create OTP challenges before a canonical client record exists.
    pass

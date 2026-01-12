"""Add clearing job type for admin runs

Revision ID: 0039_clearing_job_type
Revises: 20271220_0038_finance_invoice_extensions
Create Date: 2025-01-15 00:39:00.000000
"""

from __future__ import annotations

from alembic import op

from alembic_helpers import SCHEMA, ensure_pg_enum_value, is_postgres

# revision identifiers, used by Alembic.
revision = "0039_clearing_job_type"
down_revision = "20271220_0038_finance_invoice_extensions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not is_postgres(bind):
        return

    ensure_pg_enum_value(bind, "billing_job_type", "CLEARING", schema=SCHEMA)


def downgrade():
    # Enum value removal is intentionally skipped to keep migrations idempotent
    pass

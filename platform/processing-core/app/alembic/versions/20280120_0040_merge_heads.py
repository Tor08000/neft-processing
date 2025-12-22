"""Merge finance idempotency and clearing branches

Revision ID: 20280120_0040
Revises: 20280110_0039_billing_finance_idempotency, 20280115_0039_clearing_job_type
Create Date: 2028-01-20 00:40:00.000000
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20280120_0040"
down_revision = ("20280110_0039_billing_finance_idempotency", "20280115_0039_clearing_job_type")
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - merge only
    pass


def downgrade() -> None:  # pragma: no cover - merge only
    pass

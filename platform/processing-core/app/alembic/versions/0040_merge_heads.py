"""Merge finance idempotency and clearing branches

Revision ID: 0040_merge_heads
Revises: 0039_billing_finance_idempotency, 0039_clearing_job_type
Create Date: 2028-01-20 00:40:00.000000
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0040_merge_heads"
down_revision = ("0039_billing_finance_idempotency", "0039_clearing_job_type")
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - merge only
    pass


def downgrade() -> None:  # pragma: no cover - merge only
    pass

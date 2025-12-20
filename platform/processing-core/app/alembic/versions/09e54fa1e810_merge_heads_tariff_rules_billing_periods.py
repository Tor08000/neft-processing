"""merge heads: tariff rules + billing periods

Revision ID: 09e54fa1e810
Revises: 20270901_0031_tariff_commission_rules
Create Date: 2027-10-20
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "09e54fa1e810"

# основной родитель (одна из голов)
down_revision = "20270901_0031_tariff_commission_rules"

# вторая голова как dependency
depends_on = "20271020_0033_billing_periods"

branch_labels = None


def upgrade() -> None:
    # merge only, no DDL
    pass


def downgrade() -> None:
    # merge only, no DDL
    pass

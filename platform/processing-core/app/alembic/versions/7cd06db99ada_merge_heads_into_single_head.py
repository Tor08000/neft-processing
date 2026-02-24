"""merge heads into single head

Revision ID: 7cd06db99ada
Revises: 20299990_0189_phase3_financial_hardening, 20300120_0205_merge_heads
Create Date: 2026-02-24 15:34:47.017187
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "7cd06db99ada"
down_revision: Union[str, Sequence[str], None] = (
    "20299990_0189_phase3_financial_hardening",
    "20300120_0205_merge_heads",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

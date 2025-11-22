"""Auto-generated Alembic revision.

Revision ID: ${up_revision}
Revises: ${down_revision|comma,n}
Create Date: ${create_date}
"""

from alembic import op
import sqlalchemy as sa


# Эти переменные Alembic подставит сам
revision = "${up_revision}"
down_revision = ${down_revision|repr}
branch_labels = ${branch_labels|repr}
depends_on = ${depends_on|repr}


def upgrade() -> None:
    """Apply migration."""
    pass


def downgrade() -> None:
    """Rollback migration."""
    pass

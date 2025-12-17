"""add posting_result column to operations

Revision ID: 20270626_0027_add_posting_result_to_operations
Revises: 20270625_0026_add_accounts_to_operations
Create Date: 2027-06-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "20270626_0027_add_posting_result_to_operations"
down_revision = "20270625_0026_add_accounts_to_operations"
branch_labels = None
depends_on = None



def _json_type(bind):
    return JSONB if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "operations" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("operations")}
    if "posting_result" in column_names:
        return

    op.add_column("operations", sa.Column("posting_result", _json_type(bind), nullable=True))



def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "operations" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("operations")}
    if "posting_result" not in column_names:
        return

    op.drop_column("operations", "posting_result")

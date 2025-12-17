"""add accounts column to operations

Revision ID: 20270625_0026_add_accounts_to_operations
Revises: 20270620_0025_ledger_entries_operation_id_nullable
Create Date: 2027-06-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "20270625_0026_add_accounts_to_operations"
down_revision = "20270620_0025_ledger_entries_operation_id_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "operations" in inspector.get_table_names():
        column_names = {column["name"] for column in inspector.get_columns("operations")}

        if "accounts" not in column_names:
            op.add_column("operations", sa.Column("accounts", JSONB, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "operations" in inspector.get_table_names():
        column_names = {column["name"] for column in inspector.get_columns("operations")}

        if "accounts" in column_names:
            op.drop_column("operations", "accounts")

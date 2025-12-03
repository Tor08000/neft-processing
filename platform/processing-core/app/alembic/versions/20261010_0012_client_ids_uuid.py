"""Ensure client foreign keys use UUID"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261010_0012_client_ids_uuid"
down_revision = "20260115_0011_operations_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "clients",
        "id",
        existing_type=sa.BigInteger(),
        type_=postgresql.UUID(as_uuid=True),
        postgresql_using="id::uuid",
        existing_nullable=False,
    )
    op.execute("ALTER TABLE clients ALTER COLUMN id SET DEFAULT gen_random_uuid()")

    for table in ("client_cards", "client_operations", "client_limits"):
        op.alter_column(
            table,
            "client_id",
            existing_type=sa.BigInteger(),
            type_=postgresql.UUID(as_uuid=True),
            postgresql_using="client_id::uuid",
            existing_nullable=False,
        )


def downgrade() -> None:
    for table in ("client_limits", "client_operations", "client_cards"):
        op.alter_column(
            table,
            "client_id",
            existing_type=postgresql.UUID(as_uuid=True),
            type_=sa.BigInteger(),
            postgresql_using="client_id::text::bigint",
            existing_nullable=False,
        )

    op.alter_column(
        "clients",
        "id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.BigInteger(),
        postgresql_using="id::text::bigint",
        existing_nullable=False,
    )
    op.execute("ALTER TABLE clients ALTER COLUMN id DROP DEFAULT")

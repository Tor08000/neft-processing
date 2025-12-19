# services/core-api/app/alembic/versions/20251118_0002_operations_journal.py

from alembic import op

from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20251118_0002_operations_journal"
down_revision = "20251112_0001_core"
branch_labels = None
depends_on = None


def upgrade():
    schema_resolution = resolve_db_schema()
    schema = schema_resolution.schema
    print(f"[{revision}] {schema_resolution.line()}")

    op.create_index("ix_operations_card_id", "operations", ["card_id"], schema=schema)
    op.create_index("ix_operations_client_id", "operations", ["client_id"], schema=schema)
    op.create_index("ix_operations_merchant_id", "operations", ["merchant_id"], schema=schema)
    op.create_index("ix_operations_terminal_id", "operations", ["terminal_id"], schema=schema)
    op.create_index("ix_operations_created_at", "operations", ["created_at"], schema=schema)


def downgrade():
    schema_resolution = resolve_db_schema()
    schema = schema_resolution.schema
    print(f"[{revision}] {schema_resolution.line()}")

    op.drop_index("ix_operations_created_at", table_name="operations", schema=schema)
    op.drop_index("ix_operations_terminal_id", table_name="operations", schema=schema)
    op.drop_index("ix_operations_merchant_id", table_name="operations", schema=schema)
    op.drop_index("ix_operations_client_id", table_name="operations", schema=schema)
    op.drop_index("ix_operations_card_id", table_name="operations", schema=schema)

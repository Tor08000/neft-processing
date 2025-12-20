"""Align billing_summary with finalized status lifecycle

Revision ID: 20270831_0030_billing_state_machine
Revises: 20270720_0029_cards_created_at
Create Date: 2024-08-31 00:00:00
"""

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import (
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    ensure_pg_enum,
    is_sqlite,
    safe_enum,
)
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20270831_0030_billing_state_machine"
down_revision = "20270720_0029_cards_created_at"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema
ENUM_NAME = "billing_summary_status"
ENUM_VALUES = ["PENDING", "FINALIZED"]
INDEX_NAME = "ix_billing_summary_status_billing_date"
UNIQUE_NAME = "uq_billing_summary_unique_scope"


def upgrade():
    bind = op.get_bind()
    ensure_pg_enum(bind, ENUM_NAME, ENUM_VALUES, schema=SCHEMA)
    status_enum = safe_enum(bind, ENUM_NAME, ENUM_VALUES, schema=SCHEMA)

    if not column_exists(bind, "billing_summary", "status", schema=SCHEMA):
        op.add_column(
            "billing_summary",
            sa.Column(
                "status",
                status_enum,
                nullable=False,
                server_default=ENUM_VALUES[0],
            ),
            schema=SCHEMA,
        )
    else:
        op.execute(
            sa.text(
                f"UPDATE {SCHEMA}.billing_summary SET status=:pending WHERE status IS NULL"
            ),
            {"pending": ENUM_VALUES[0]},
        )
        if not is_sqlite(bind):
            op.alter_column(
                "billing_summary",
                "status",
                existing_type=status_enum,
                server_default=ENUM_VALUES[0],
                nullable=False,
                schema=SCHEMA,
            )

    if not column_exists(bind, "billing_summary", "finalized_at", schema=SCHEMA):
        op.add_column(
            "billing_summary",
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )

    if not constraint_exists(bind, "billing_summary", UNIQUE_NAME, schema=SCHEMA):
        op.create_unique_constraint(
            UNIQUE_NAME,
            "billing_summary",
            ["billing_date", "merchant_id", "client_id", "product_type", "currency"],
            schema=SCHEMA,
        )

    index_schema = None if is_sqlite(bind) else SCHEMA
    create_index_if_not_exists(
        bind,
        INDEX_NAME,
        "billing_summary",
        ["status", "billing_date"],
        schema=index_schema,
    )


def downgrade():
    bind = op.get_bind()

    if not is_sqlite(bind):
        op.alter_column(
            "billing_summary",
            "status",
            existing_type=safe_enum(bind, ENUM_NAME, ENUM_VALUES, schema=SCHEMA),
            nullable=True,
            schema=SCHEMA,
        )

    if column_exists(bind, "billing_summary", "finalized_at", schema=SCHEMA):
        op.drop_column("billing_summary", "finalized_at", schema=SCHEMA)

    if constraint_exists(bind, "billing_summary", UNIQUE_NAME, schema=SCHEMA):
        op.drop_constraint(UNIQUE_NAME, "billing_summary", schema=SCHEMA)

    if not is_sqlite(bind):
        op.drop_index(INDEX_NAME, table_name="billing_summary", schema=SCHEMA)
    else:
        op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")

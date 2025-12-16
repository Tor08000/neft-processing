"""client portal tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.alembic.utils import (
    column_exists,
    constraint_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    drop_table_if_exists,
    table_exists,
)

# revision identifiers, used by Alembic.
revision = "20260701_0009_client_portal"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "clients"):
        if not column_exists(bind, "clients", "email"):
            op.add_column("clients", sa.Column("email", sa.String(), nullable=True))
        if not column_exists(bind, "clients", "full_name"):
            op.add_column("clients", sa.Column("full_name", sa.String(), nullable=True))
        if not column_exists(bind, "clients", "status"):
            op.add_column(
                "clients",
                sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
            )
        if not constraint_exists(bind, "clients", "uq_clients_email"):
            op.create_unique_constraint("uq_clients_email", "clients", ["email"])

    create_table_if_not_exists(
        bind,
        "client_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.String(), nullable=False),
        sa.Column("pan_masked", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name="fk_client_cards_client"),
    )
    create_index_if_not_exists(bind, "ix_client_cards_client_id", "client_cards", ["client_id"])
    create_index_if_not_exists(bind, "ix_client_cards_card_id", "client_cards", ["card_id"])

    create_table_if_not_exists(
        bind,
        "client_operations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", sa.String(), nullable=True),
        sa.Column("operation_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("fuel_type", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name="fk_client_operations_client"),
    )
    create_index_if_not_exists(bind, "ix_client_operations_client_id", "client_operations", ["client_id"])
    create_index_if_not_exists(bind, "ix_client_operations_card_id", "client_operations", ["card_id"])
    create_index_if_not_exists(
        bind, "ix_client_operations_operation_type", "client_operations", ["operation_type"]
    )
    create_index_if_not_exists(bind, "ix_client_operations_status", "client_operations", ["status"])

    create_table_if_not_exists(
        bind,
        "client_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("limit_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("used_amount", sa.Numeric(), server_default="0", nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name="fk_client_limits_client"),
    )
    create_index_if_not_exists(bind, "ix_client_limits_client_id", "client_limits", ["client_id"])


def downgrade() -> None:
    bind = op.get_bind()
    drop_table_if_exists(bind, "client_limits")
    drop_table_if_exists(bind, "client_operations")
    drop_table_if_exists(bind, "client_cards")
    if table_exists(bind, "clients") and constraint_exists(bind, "clients", "uq_clients_email"):
        op.drop_constraint("uq_clients_email", "clients", type_="unique")
    if table_exists(bind, "clients") and column_exists(bind, "clients", "status"):
        op.drop_column("clients", "status")
    if table_exists(bind, "clients") and column_exists(bind, "clients", "full_name"):
        op.drop_column("clients", "full_name")
    if table_exists(bind, "clients") and column_exists(bind, "clients", "email"):
        op.drop_column("clients", "email")

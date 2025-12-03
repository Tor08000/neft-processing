"""client portal tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260701_0009_client_portal"
down_revision = "20260101_0008_billing_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("email", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column(
        "clients",
        sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
    )
    op.create_unique_constraint("uq_clients_email", "clients", ["email"])

    op.create_table(
        "client_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("card_id", sa.String(), nullable=False, index=True),
        sa.Column("pan_masked", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name="fk_client_cards_client"),
    )

    op.create_table(
        "client_operations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("card_id", sa.String(), nullable=True, index=True),
        sa.Column("operation_type", sa.String(), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, index=True),
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

    op.create_table(
        "client_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("limit_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="RUB", nullable=False),
        sa.Column("used_amount", sa.Numeric(), server_default="0", nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name="fk_client_limits_client"),
    )


def downgrade() -> None:
    op.drop_table("client_limits")
    op.drop_table("client_operations")
    op.drop_table("client_cards")
    op.drop_constraint("uq_clients_email", "clients", type_="unique")
    op.drop_column("clients", "status")
    op.drop_column("clients", "full_name")
    op.drop_column("clients", "email")

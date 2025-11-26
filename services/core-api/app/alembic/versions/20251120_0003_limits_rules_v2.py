# services/core-api/app/alembic/versions/20251120_0003_limits_rules_v2.py

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251120_0003_limits_rules_v2"
down_revision = "20251118_0002_operations_journal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "limits_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phase", sa.String(length=16), nullable=False, server_default="AUTH"),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("card_id", sa.String(length=64), nullable=True),
        sa.Column("merchant_id", sa.String(length=64), nullable=True),
        sa.Column("terminal_id", sa.String(length=64), nullable=True),
        sa.Column("client_group_id", sa.String(length=64), nullable=True),
        sa.Column("card_group_id", sa.String(length=64), nullable=True),
        sa.Column("product_category", sa.String(length=64), nullable=True),
        sa.Column("mcc", sa.String(length=32), nullable=True),
        sa.Column("tx_type", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("daily_limit", sa.BigInteger(), nullable=True),
        sa.Column("limit_per_tx", sa.BigInteger(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_index("ix_limits_rules_product_category", "limits_rules", ["product_category"])
    op.create_index("ix_limits_rules_mcc", "limits_rules", ["mcc"])
    op.create_index("ix_limits_rules_tx_type", "limits_rules", ["tx_type"])
    op.create_index("ix_limits_rules_client_group_id", "limits_rules", ["client_group_id"])
    op.create_index("ix_limits_rules_card_group_id", "limits_rules", ["card_group_id"])

    op.add_column(
        "operations",
        sa.Column("tx_type", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_operations_tx_type", "operations", ["tx_type"])


def downgrade():
    op.drop_index("ix_operations_tx_type", table_name="operations")
    op.drop_column("operations", "tx_type")

    op.drop_index("ix_limits_rules_card_group_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_client_group_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_tx_type", table_name="limits_rules")
    op.drop_index("ix_limits_rules_mcc", table_name="limits_rules")
    op.drop_index("ix_limits_rules_product_category", table_name="limits_rules")

    op.drop_table("limits_rules")

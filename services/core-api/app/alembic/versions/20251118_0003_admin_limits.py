# services/core-api/app/alembic/versions/20251118_0003_admin_limits.py

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251118_0003_admin_limits"
down_revision = "20251118_0002_operations_journal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "client_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id"),
    )
    op.create_index("ix_client_groups_group_id", "client_groups", ["group_id"], unique=False)

    op.create_table(
        "card_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id"),
    )
    op.create_index("ix_card_groups_group_id", "card_groups", ["group_id"], unique=False)

    op.create_table(
        "client_group_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_group_id", sa.Integer(), sa.ForeignKey("client_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("client_group_id", "client_id", name="uq_client_group_member"),
    )

    op.create_table(
        "card_group_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("card_group_id", sa.Integer(), sa.ForeignKey("card_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("card_group_id", "card_id", name="uq_card_group_member"),
    )

    op.create_table(
        "limits_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phase", sa.String(length=16), nullable=False, server_default="AUTH"),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("card_id", sa.String(length=64), nullable=True),
        sa.Column("merchant_id", sa.String(length=64), nullable=True),
        sa.Column("terminal_id", sa.String(length=64), nullable=True),
        sa.Column("client_group_id", sa.String(length=64), nullable=True),
        sa.Column("card_group_id", sa.String(length=64), nullable=True),
        sa.Column("product_category", sa.String(length=64), nullable=True),
        sa.Column("mcc", sa.String(length=64), nullable=True),
        sa.Column("tx_type", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("limit_per_tx", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_index("ix_limits_rules_client_id", "limits_rules", ["client_id"])
    op.create_index("ix_limits_rules_card_id", "limits_rules", ["card_id"])
    op.create_index("ix_limits_rules_merchant_id", "limits_rules", ["merchant_id"])
    op.create_index("ix_limits_rules_terminal_id", "limits_rules", ["terminal_id"])
    op.create_index("ix_limits_rules_client_group_id", "limits_rules", ["client_group_id"])
    op.create_index("ix_limits_rules_card_group_id", "limits_rules", ["card_group_id"])
    op.create_index("ix_limits_rules_product_category", "limits_rules", ["product_category"])
    op.create_index("ix_limits_rules_mcc", "limits_rules", ["mcc"])
    op.create_index("ix_limits_rules_tx_type", "limits_rules", ["tx_type"])


def downgrade():
    op.drop_index("ix_limits_rules_tx_type", table_name="limits_rules")
    op.drop_index("ix_limits_rules_mcc", table_name="limits_rules")
    op.drop_index("ix_limits_rules_product_category", table_name="limits_rules")
    op.drop_index("ix_limits_rules_card_group_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_client_group_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_terminal_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_merchant_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_card_id", table_name="limits_rules")
    op.drop_index("ix_limits_rules_client_id", table_name="limits_rules")
    op.drop_table("limits_rules")

    op.drop_table("card_group_members")
    op.drop_table("client_group_members")
    op.drop_index("ix_card_groups_group_id", table_name="card_groups")
    op.drop_table("card_groups")
    op.drop_index("ix_client_groups_group_id", table_name="client_groups")
    op.drop_table("client_groups")

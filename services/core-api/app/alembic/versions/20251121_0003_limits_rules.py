# services/core-api/app/alembic/versions/20251121_0003_limits_rules.py

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251121_0003_limits_rules"
down_revision = "20251118_0002_operations_journal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "client_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "card_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "client_group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("client_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("group_id", "client_id", name="uq_client_group_member"),
    )
    op.create_index(
        "ix_client_group_memberships_client_id",
        "client_group_memberships",
        ["client_id"],
    )

    op.create_table(
        "card_group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("card_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_id", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("group_id", "card_id", name="uq_card_group_member"),
    )
    op.create_index(
        "ix_card_group_memberships_card_id",
        "card_group_memberships",
        ["card_id"],
    )

    op.create_table(
        "limits_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, index=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_limit", sa.BigInteger(), nullable=False),
        sa.Column("limit_per_tx", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column(
            "client_group_id",
            sa.Integer(),
            sa.ForeignKey("client_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "card_group_id",
            sa.Integer(),
            sa.ForeignKey("card_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_limits_rules_priority", "limits_rules", ["priority"])


def downgrade():
    op.drop_index("ix_limits_rules_priority", table_name="limits_rules")
    op.drop_table("limits_rules")

    op.drop_index("ix_card_group_memberships_card_id", table_name="card_group_memberships")
    op.drop_table("card_group_memberships")

    op.drop_index("ix_client_group_memberships_client_id", table_name="client_group_memberships")
    op.drop_table("client_group_memberships")

    op.drop_table("card_groups")
    op.drop_table("client_groups")

"""auto fix schema alignment

Revision ID: 20251220_0006_auto_fix
Revises: 20251215_0005_add_created_at_to_cards
Create Date: 2025-12-20 00:06:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20251220_0006_auto_fix"
down_revision = "20251215_0005_add_created_at_to_cards"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table: str, name: str) -> bool:
    return any(index.get("name") == name for index in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Ensure group tables are present
    if not _table_exists(inspector, "client_groups"):
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

    if not _table_exists(inspector, "card_groups"):
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

    if not _table_exists(inspector, "client_group_members"):
        op.create_table(
            "client_group_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "client_group_id",
                sa.Integer(),
                sa.ForeignKey("client_groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.UniqueConstraint("client_group_id", "client_id", name="uq_client_group_member"),
        )

    if not _table_exists(inspector, "card_group_members"):
        op.create_table(
            "card_group_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "card_group_id",
                sa.Integer(),
                sa.ForeignKey("card_groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("card_id", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.UniqueConstraint("card_group_id", "card_id", name="uq_card_group_member"),
        )

    # Align operations columns
    if _table_exists(inspector, "operations"):
        columns = {col["name"]: col for col in inspector.get_columns("operations")}

        desired_columns = {
            "mcc": sa.String(length=8),
            "product_code": sa.String(length=32),
            "product_category": sa.String(length=32),
            "tx_type": sa.String(length=16),
        }

        for name, col_type in desired_columns.items():
            if name in columns:
                op.alter_column(
                    "operations",
                    name,
                    existing_type=columns[name]["type"],
                    type_=col_type,
                )
            else:
                op.add_column("operations", sa.Column(name, col_type, nullable=True))

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("operations")}
        index_mapping = {
            "ix_operations_mcc": ["mcc"],
            "ix_operations_product_category": ["product_category"],
            "ix_operations_tx_type": ["tx_type"],
        }
        for index_name, columns_list in index_mapping.items():
            if index_name not in existing_indexes:
                op.create_index(index_name, "operations", columns_list)

    # Align cards table
    if _table_exists(inspector, "cards"):
        columns = {col["name"]: col for col in inspector.get_columns("cards")}

        # Ensure columns exist
        if "pan_masked" not in columns:
            op.add_column("cards", sa.Column("pan_masked", sa.String(length=32), nullable=True))
        if "expires_at" not in columns:
            op.add_column("cards", sa.Column("expires_at", sa.String(length=16), nullable=True))
        if "created_at" not in columns:
            op.add_column(
                "cards",
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("NOW()"),
                    nullable=False,
                ),
            )
        else:
            op.alter_column(
                "cards",
                "created_at",
                existing_type=columns["created_at"]["type"],
                server_default=sa.text("NOW()"),
                nullable=False,
            )

        # Ensure types align with ORM expectations
        id_column = columns.get("id")
        if id_column is not None and not isinstance(id_column["type"], sa.String):
            op.alter_column(
                "cards",
                "id",
                existing_type=id_column["type"],
                type_=sa.String(length=64),
                nullable=False,
                server_default=None,
                postgresql_using="id::text",
            )
        client_id_column = columns.get("client_id")
        if client_id_column is not None and not isinstance(client_id_column["type"], sa.String):
            op.alter_column(
                "cards",
                "client_id",
                existing_type=client_id_column["type"],
                type_=sa.String(length=64),
                nullable=False,
                postgresql_using="client_id::text",
            )
        status_column = columns.get("status")
        if status_column is not None and not isinstance(status_column["type"], sa.String):
            op.alter_column(
                "cards",
                "status",
                existing_type=status_column["type"],
                type_=sa.String(length=32),
                nullable=False,
                postgresql_using="status::text",
            )

        # Ensure indexes exist
        if not _index_exists(inspector, "cards", "ix_cards_id"):
            op.create_index("ix_cards_id", "cards", ["id"], unique=False)
        if not _index_exists(inspector, "cards", "ix_cards_client_id"):
            op.create_index("ix_cards_client_id", "cards", ["client_id"], unique=False)
        if not _index_exists(inspector, "cards", "ix_cards_status"):
            op.create_index("ix_cards_status", "cards", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if _table_exists(inspector, "card_group_members"):
        op.drop_table("card_group_members")
    if _table_exists(inspector, "client_group_members"):
        op.drop_table("client_group_members")
    if _index_exists(inspector, "card_groups", "ix_card_groups_group_id"):
        op.drop_index("ix_card_groups_group_id", table_name="card_groups")
    if _table_exists(inspector, "card_groups"):
        op.drop_table("card_groups")
    if _index_exists(inspector, "client_groups", "ix_client_groups_group_id"):
        op.drop_index("ix_client_groups_group_id", table_name="client_groups")
    if _table_exists(inspector, "client_groups"):
        op.drop_table("client_groups")

    if _index_exists(inspector, "cards", "ix_cards_status"):
        op.drop_index("ix_cards_status", table_name="cards")
    if _index_exists(inspector, "cards", "ix_cards_client_id"):
        op.drop_index("ix_cards_client_id", table_name="cards")
    if _index_exists(inspector, "cards", "ix_cards_id"):
        op.drop_index("ix_cards_id", table_name="cards")

    if _table_exists(inspector, "operations"):
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("operations")]
        if "ix_operations_tx_type" in existing_indexes:
            op.drop_index("ix_operations_tx_type", table_name="operations")
        if "ix_operations_product_category" in existing_indexes:
            op.drop_index("ix_operations_product_category", table_name="operations")
        if "ix_operations_mcc" in existing_indexes:
            op.drop_index("ix_operations_mcc", table_name="operations")

        for column in ("tx_type", "product_category", "product_code", "mcc"):
            if column in [col["name"] for col in inspector.get_columns("operations")]:
                op.drop_column("operations", column)

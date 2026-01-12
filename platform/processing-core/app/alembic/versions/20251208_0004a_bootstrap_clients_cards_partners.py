"""bootstrap clients/cards/partners tables

Revision ID: 20251208_0004a_bootstrap_clients_cards_partners
Revises: 20251206_0004_operations_product_fields
Create Date: 2025-12-08 00:04:00.000000
"""

from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic_helpers import constraint_exists, create_index_if_not_exists, create_table_if_not_exists
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20251208_0004a_bootstrap_clients_cards_partners"
down_revision = "20251206_0004_operations_product_fields"
branch_labels = None
depends_on = None

SCHEMA_RESOLUTION = resolve_db_schema()
SCHEMA = SCHEMA_RESOLUTION.schema


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _missing_columns(inspector: sa.Inspector, table: str, expected: Iterable[str]) -> set[str]:
    existing = {col["name"] for col in inspector.get_columns(table)}
    return set(expected) - existing


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _table_exists(inspector, "clients"):
        create_table_if_not_exists(
            bind,
            "clients",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("external_id", sa.String(), nullable=True),
            sa.Column("inn", sa.String(), nullable=True),
            sa.Column("tariff_plan", sa.String(), nullable=True),
            sa.Column("account_manager", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.UniqueConstraint("external_id", name="uq_clients_external_id"),
        )
        create_index_if_not_exists(bind, "ix_clients_id", "clients", ["id"], unique=False)
    else:
        missing_columns = _missing_columns(
            inspector,
            "clients",
            ["external_id", "inn", "tariff_plan", "account_manager", "created_at"],
        )
        if "external_id" in missing_columns:
            op.add_column("clients", sa.Column("external_id", sa.String(), nullable=True))
            if not constraint_exists(bind, "clients", "uq_clients_external_id", schema=SCHEMA):
                op.create_unique_constraint("uq_clients_external_id", "clients", ["external_id"], schema=SCHEMA)
        if "inn" in missing_columns:
            op.add_column("clients", sa.Column("inn", sa.String(), nullable=True))
        if "tariff_plan" in missing_columns:
            op.add_column("clients", sa.Column("tariff_plan", sa.String(), nullable=True))
        if "account_manager" in missing_columns:
            op.add_column("clients", sa.Column("account_manager", sa.String(), nullable=True))
        if "created_at" in missing_columns:
            op.add_column(
                "clients",
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("NOW()"),
                    nullable=False,
                ),
            )
        create_index_if_not_exists(bind, "ix_clients_id", "clients", ["id"], unique=False)

    if not _table_exists(inspector, "cards"):
        create_table_if_not_exists(
            bind,
            "cards",
            sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("pan_masked", sa.String(length=32), nullable=True),
            sa.Column("expires_at", sa.String(length=16), nullable=True),
        )
        create_index_if_not_exists(bind, "ix_cards_id", "cards", ["id"], unique=False)
        create_index_if_not_exists(bind, "ix_cards_client_id", "cards", ["client_id"], unique=False)
        create_index_if_not_exists(bind, "ix_cards_status", "cards", ["status"], unique=False)
    else:
        missing_columns = _missing_columns(
            inspector,
            "cards",
            ["pan_masked", "expires_at"],
        )
        if "pan_masked" in missing_columns:
            op.add_column("cards", sa.Column("pan_masked", sa.String(length=32), nullable=True))
        if "expires_at" in missing_columns:
            op.add_column("cards", sa.Column("expires_at", sa.String(length=16), nullable=True))
        for index_name, columns in (
            ("ix_cards_id", ["id"]),
            ("ix_cards_client_id", ["client_id"]),
            ("ix_cards_status", ["status"]),
        ):
            create_index_if_not_exists(bind, index_name, "cards", columns, unique=False)

    if not _table_exists(inspector, "partners"):
        allowed_ips_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
        create_table_if_not_exists(
            bind,
            "partners",
            sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column(
                "allowed_ips",
                allowed_ips_type,
                nullable=True,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        create_index_if_not_exists(bind, "ix_partners_status", "partners", ["status"], unique=False)
    else:
        missing_columns = _missing_columns(
            inspector,
            "partners",
            ["allowed_ips", "token", "status", "created_at"],
        )
        if "allowed_ips" in missing_columns:
            op.add_column(
                "partners",
                sa.Column(
                    "allowed_ips",
                    sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                    nullable=True,
                    server_default=sa.text("'[]'::jsonb"),
                ),
            )
        if "token" in missing_columns:
            op.add_column("partners", sa.Column("token", sa.String(length=255), nullable=False, server_default=""))
        if "status" in missing_columns:
            op.add_column(
                "partners",
                sa.Column(
                    "status",
                    sa.String(length=32),
                    nullable=False,
                    server_default="active",
                ),
            )
        if "created_at" in missing_columns:
            op.add_column(
                "partners",
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now(),
                ),
            )
        create_index_if_not_exists(bind, "ix_partners_status", "partners", ["status"], unique=False)


def downgrade() -> None:
    # Forward-only migration set: no downgrade.
    pass

"""Legal graph v1 tables.

Revision ID: 20291215_0057_legal_graph_v1
Revises: 20291201_0056_internal_ledger_v1
Create Date: 2029-12-15 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from alembic_helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20291215_0057_legal_graph_v1"
down_revision = "20291201_0056_internal_ledger_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

NODE_TYPES = [
    "DOCUMENT",
    "CLOSING_PACKAGE",
    "BILLING_PERIOD",
    "INVOICE",
    "PAYMENT",
    "CREDIT_NOTE",
    "REFUND",
    "SETTLEMENT_ALLOCATION",
    "ACCOUNTING_EXPORT_BATCH",
    "RISK_DECISION",
    "OFFER",
]
EDGE_TYPES = [
    "GENERATED_FROM",
    "CONFIRMS",
    "CLOSES",
    "INCLUDES",
    "RELATES_TO",
    "SIGNED_BY",
    "RISK_GATED_BY",
    "SETTLES",
    "EXPORTS",
    "REPLACES",
]
SNAPSHOT_SCOPE_TYPES = [
    "DOCUMENT",
    "CLOSING_PACKAGE",
    "BILLING_PERIOD",
]


def _uuid_type(bind):
    if getattr(bind.dialect, "name", None) == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "legal_node_type", NODE_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_edge_type", EDGE_TYPES, schema=SCHEMA)
    ensure_pg_enum(bind, "legal_graph_snapshot_scope", SNAPSHOT_SCOPE_TYPES, schema=SCHEMA)

    node_type_enum = safe_enum(bind, "legal_node_type", NODE_TYPES, schema=SCHEMA)
    edge_type_enum = safe_enum(bind, "legal_edge_type", EDGE_TYPES, schema=SCHEMA)
    scope_type_enum = safe_enum(bind, "legal_graph_snapshot_scope", SNAPSHOT_SCOPE_TYPES, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "legal_nodes",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("node_type", node_type_enum, nullable=False),
        sa.Column("ref_id", sa.String(length=128), nullable=False),
        sa.Column("ref_table", sa.String(length=64), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "node_type", "ref_id", name="uq_legal_nodes_scope"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_nodes_type_ref",
        "legal_nodes",
        ["node_type", "ref_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_nodes_tenant_type",
        "legal_nodes",
        ["tenant_id", "node_type"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "legal_edges",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("edge_type", edge_type_enum, nullable=False),
        sa.Column("src_node_id", _uuid_type(bind), sa.ForeignKey(f"{SCHEMA}.legal_nodes.id"), nullable=False),
        sa.Column("dst_node_id", _uuid_type(bind), sa.ForeignKey(f"{SCHEMA}.legal_nodes.id"), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "edge_type", "src_node_id", "dst_node_id", name="uq_legal_edges_scope"),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_edges_src",
        "legal_edges",
        ["src_node_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_edges_dst",
        "legal_edges",
        ["dst_node_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_edges_type",
        "legal_edges",
        ["edge_type"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "legal_graph_snapshots",
        sa.Column("id", _uuid_type(bind), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("scope_type", scope_type_enum, nullable=False),
        sa.Column("scope_ref_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("nodes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edges_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=True),
        sa.Column("created_by_actor_id", sa.String(length=64), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_ref_id",
            "snapshot_hash",
            name="uq_legal_graph_snapshots_scope",
        ),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_legal_graph_snapshots_scope",
        "legal_graph_snapshots",
        ["tenant_id", "scope_type", "scope_ref_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("legal_graph_snapshots", schema=SCHEMA)
    op.drop_table("legal_edges", schema=SCHEMA)
    op.drop_table("legal_nodes", schema=SCHEMA)

    if getattr(bind.dialect, "name", None) != "postgresql":
        return
    bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA}.legal_graph_snapshot_scope")
    bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA}.legal_edge_type")
    bind.exec_driver_sql(f"DROP TYPE IF EXISTS {SCHEMA}.legal_node_type")

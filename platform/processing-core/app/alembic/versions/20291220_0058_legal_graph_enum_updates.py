"""Add legal graph enum values for document files/acks and edge types.

Revision ID: 20291220_0058_legal_graph_enum_updates
Revises: 20291215_0057_legal_graph_v1
Create Date: 2029-12-20 00:00:00
"""

from __future__ import annotations

from alembic import op

from app.alembic.helpers import ensure_pg_enum_value, is_postgres
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20291220_0058_legal_graph_enum_updates"
down_revision = "20291215_0057_legal_graph_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

NODE_VALUES = ["DOCUMENT_FILE", "DOCUMENT_ACK"]
EDGE_VALUES = ["GATED_BY_RISK", "ALLOCATES", "OVERRIDDEN_BY"]


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    for value in NODE_VALUES:
        ensure_pg_enum_value(bind, "legal_node_type", value, schema=SCHEMA)
    for value in EDGE_VALUES:
        ensure_pg_enum_value(bind, "legal_edge_type", value, schema=SCHEMA)


def downgrade() -> None:
    # Enum values are intentionally left in place.
    pass

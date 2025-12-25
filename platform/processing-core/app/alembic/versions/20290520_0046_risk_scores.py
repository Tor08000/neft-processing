"""Add risk scores table.

Revision ID: 20290520_0046_risk_scores
Revises: 20290501_0045_document_status_lifecycle
Create Date: 2029-05-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import create_index_if_not_exists, create_table_if_not_exists, ensure_pg_enum, safe_enum
from app.db.types import GUID
from app.db.schema import resolve_db_schema

revision = "20290520_0046_risk_scores"
down_revision = "20290501_0045_document_status_lifecycle"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

RISK_SCORE_ACTIONS = ["PAYMENT", "INVOICE", "PAYOUT"]
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "risk_score_action", RISK_SCORE_ACTIONS, schema=SCHEMA)
    ensure_pg_enum(bind, "risk_level", RISK_LEVELS, schema=SCHEMA)
    action_enum = safe_enum(bind, "risk_score_action", RISK_SCORE_ACTIONS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "risk_scores",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", action_enum, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )

    create_index_if_not_exists(
        bind,
        "ix_risk_score_actor",
        "risk_scores",
        ["actor_id"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_risk_score_action",
        "risk_scores",
        ["action"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass

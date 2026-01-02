"""Case event signatures metadata.

Revision ID: 20291790_0096_case_event_signatures
Revises: 20291780_0095_audit_retention_worm
Create Date: 2025-03-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.helpers import column_exists, table_exists
from app.db.schema import resolve_db_schema

revision = "20291790_0096_case_event_signatures"
down_revision = "20291780_0095_audit_retention_worm"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "case_events", schema=SCHEMA):
        return
    table_name = "case_events"
    if not column_exists(bind, table_name, "signature_alg", schema=SCHEMA):
        op.add_column(table_name, sa.Column("signature_alg", sa.String(length=64), nullable=True), schema=SCHEMA)
    if not column_exists(bind, table_name, "signing_key_id", schema=SCHEMA):
        op.add_column(table_name, sa.Column("signing_key_id", sa.String(length=256), nullable=True), schema=SCHEMA)
    if not column_exists(bind, table_name, "signed_at", schema=SCHEMA):
        op.add_column(table_name, sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    pass

"""Case events hash chain.

Revision ID: 20291770_0094_case_events_hash_chain
Revises: 20291760_0093_seed_subscription_packages_v1
Create Date: 2025-03-06 00:00:00.000000
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

import sqlalchemy as sa
from alembic import op

from alembic_helpers import (
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    safe_enum,
    table_exists,
)
from db.schema import resolve_db_schema


revision = "20291770_0094_case_events_hash_chain"
down_revision = "20291760_0093_seed_subscription_packages_v1"
branch_labels = None
depends_on = None

SCHEMA = resolve_db_schema().schema

CASE_EVENT_TYPES = [
    "CASE_CREATED",
    "STATUS_CHANGED",
    "CASE_CLOSED",
    "NOTE_UPDATED",
    "ACTIONS_APPLIED",
    "EXPORT_CREATED",
]


def _schema_prefix() -> str:
    return f"{SCHEMA}." if SCHEMA else ""


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime):
            resolved = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return resolved.astimezone(timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_value(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    normalized = _normalize_value(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _strip_redaction_hash(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_redaction_hash(item) for item in value]
    if isinstance(value, dict):
        if value.get("redacted") is True:
            return {key: item for key, item in value.items() if key != "hash"}
        return {key: _strip_redaction_hash(item) for key, item in value.items()}
    return value


def _compute_hash(prev_hash: str, payload: Any) -> str:
    canonical = _canonical_json(_strip_redaction_hash(payload))
    material = f"{prev_hash}\n{canonical}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _backfill_chain(bind) -> None:
    if not table_exists(bind, "case_events", schema=SCHEMA):
        return

    rows = bind.execute(
        sa.text(
            f"""
            SELECT DISTINCT case_id
            FROM {_schema_prefix()}case_events
            WHERE hash IS NULL OR seq IS NULL OR prev_hash IS NULL
            """
        )
    ).fetchall()
    if not rows:
        return

    for (case_id,) in rows:
        events = bind.execute(
            sa.text(
                f"""
                SELECT id, payload_redacted
                FROM {_schema_prefix()}case_events
                WHERE case_id = :case_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"case_id": case_id},
        ).fetchall()
        prev_hash = "GENESIS"
        for index, event in enumerate(events, start=1):
            payload = event[1]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            event_hash = _compute_hash(prev_hash, payload)
            bind.execute(
                sa.text(
                    f"""
                    UPDATE {_schema_prefix()}case_events
                    SET seq = :seq,
                        prev_hash = :prev_hash,
                        hash = :hash
                    WHERE id = :id
                    """
                ),
                {
                    "seq": index,
                    "prev_hash": prev_hash,
                    "hash": event_hash,
                    "id": event[0],
                },
            )
            prev_hash = event_hash


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "case_event_type", CASE_EVENT_TYPES, schema=SCHEMA)
    event_enum = safe_enum(bind, "case_event_type", CASE_EVENT_TYPES, schema=SCHEMA)

    if not table_exists(bind, "case_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "case_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("seq", sa.BigInteger(), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("type", event_enum, nullable=False),
            sa.Column("actor_user_id", sa.String(length=128), nullable=True),
            sa.Column("actor_email", sa.String(length=256), nullable=True),
            sa.Column("request_id", sa.String(length=128), nullable=True),
            sa.Column("trace_id", sa.String(length=128), nullable=True),
            sa.Column("payload_redacted", sa.JSON(), nullable=False),
            sa.Column("prev_hash", sa.Text(), nullable=False),
            sa.Column("hash", sa.Text(), nullable=False),
            sa.Column("signature", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=SCHEMA,
        )
    else:
        table_name = "case_events"
        if not column_exists(bind, table_name, "seq", schema=SCHEMA):
            op.add_column(table_name, sa.Column("seq", sa.BigInteger(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "payload_redacted", schema=SCHEMA):
            op.add_column(table_name, sa.Column("payload_redacted", sa.JSON(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "prev_hash", schema=SCHEMA):
            op.add_column(table_name, sa.Column("prev_hash", sa.Text(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "hash", schema=SCHEMA):
            op.add_column(table_name, sa.Column("hash", sa.Text(), nullable=True), schema=SCHEMA)
        if not column_exists(bind, table_name, "signature", schema=SCHEMA):
            op.add_column(table_name, sa.Column("signature", sa.Text(), nullable=True), schema=SCHEMA)

    create_unique_index_if_not_exists(
        bind,
        "ux_case_events_case_seq",
        "case_events",
        ["case_id", "seq"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_case_events_case_at", "case_events", ["case_id", "at"], schema=SCHEMA)
    create_index_if_not_exists(bind, "ix_case_events_case_id", "case_events", ["case_id", "id"], schema=SCHEMA)

    _backfill_chain(bind)


def downgrade() -> None:
    pass

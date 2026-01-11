"""EDO SBIS core tables.

Revision ID: 20297230_0128_edo_v2
Revises: 20297220_0127_subscription_event_price_version_capture
Create Date: 2029-08-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

from app.alembic.utils import (
    SCHEMA,
    column_exists,
    create_index_if_not_exists,
    create_table_if_not_exists,
    create_unique_index_if_not_exists,
    ensure_pg_enum,
    is_postgres,
    safe_enum,
    table_exists,
)
from app.db.types import GUID


revision = "20297230_0128_edo_v2"
down_revision = "20297220_0127_subscription_event_price_version_capture"
branch_labels = None
depends_on = None


EDO_PROVIDER = ["SBIS"]
EDO_DOCUMENT_STATUS = [
    "DRAFT",
    "QUEUED",
    "SENDING",
    "SENT",
    "DELIVERED",
    "SIGNED",
    "REJECTED",
    "REVOKED",
    "FAILED",
    "UNKNOWN",
]
EDO_SUBJECT_TYPE = ["CLIENT", "PARTNER", "INTERNAL"]
EDO_DOCUMENT_KIND = ["CONTRACT", "INVOICE", "ACT", "RECON", "CLOSING", "OTHER"]
EDO_COUNTERPARTY_SUBJECT_TYPE = ["CLIENT", "PARTNER"]
EDO_INBOUND_STATUS = ["RECEIVED", "PROCESSED", "FAILED"]
EDO_ARTIFACT_TYPE = ["SIGNED_PACKAGE", "SIGNATURE", "RECEIPT", "PROTOCOL", "OTHER"]
EDO_TRANSITION_ACTOR_TYPE = ["SYSTEM", "USER", "PROVIDER"]
EDO_OUTBOX_STATUS = ["PENDING", "SENT", "FAILED", "DEAD"]

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "edo_provider_v2", EDO_PROVIDER, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_document_status_v2", EDO_DOCUMENT_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_subject_type", EDO_SUBJECT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_document_kind", EDO_DOCUMENT_KIND, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_counterparty_subject_type", EDO_COUNTERPARTY_SUBJECT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_inbound_status", EDO_INBOUND_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_artifact_type", EDO_ARTIFACT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_transition_actor_type", EDO_TRANSITION_ACTOR_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "edo_outbox_status", EDO_OUTBOX_STATUS, schema=SCHEMA)

    provider_enum = safe_enum(bind, "edo_provider_v2", EDO_PROVIDER, schema=SCHEMA)
    status_enum = safe_enum(bind, "edo_document_status_v2", EDO_DOCUMENT_STATUS, schema=SCHEMA)
    subject_enum = safe_enum(bind, "edo_subject_type", EDO_SUBJECT_TYPE, schema=SCHEMA)
    kind_enum = safe_enum(bind, "edo_document_kind", EDO_DOCUMENT_KIND, schema=SCHEMA)
    counterparty_subject_enum = safe_enum(bind, "edo_counterparty_subject_type", EDO_COUNTERPARTY_SUBJECT_TYPE, schema=SCHEMA)
    inbound_status_enum = safe_enum(bind, "edo_inbound_status", EDO_INBOUND_STATUS, schema=SCHEMA)
    artifact_enum = safe_enum(bind, "edo_artifact_type", EDO_ARTIFACT_TYPE, schema=SCHEMA)
    actor_enum = safe_enum(bind, "edo_transition_actor_type", EDO_TRANSITION_ACTOR_TYPE, schema=SCHEMA)
    outbox_enum = safe_enum(bind, "edo_outbox_status", EDO_OUTBOX_STATUS, schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "edo_accounts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("org_inn", sa.String(length=32), nullable=True),
        sa.Column("box_id", sa.String(length=128), nullable=False),
        sa.Column("credentials_ref", sa.String(length=256), nullable=False),
        sa.Column("webhook_secret_ref", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "edo_counterparties",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("subject_type", counterparty_subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("provider_counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("provider_box_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_edo_counterparty_mapping",
        "edo_counterparties",
        ["provider", "subject_type", "subject_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "edo_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("account_id", GUID(), sa.ForeignKey("edo_accounts.id"), nullable=False),
        sa.Column("subject_type", subject_enum, nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("document_registry_id", GUID(), nullable=False),
        sa.Column("document_kind", kind_enum, nullable=False),
        sa.Column("provider_doc_id", sa.String(length=128), nullable=True),
        sa.Column("provider_thread_id", sa.String(length=128), nullable=True),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("counterparty_id", GUID(), sa.ForeignKey("edo_counterparties.id"), nullable=False),
        sa.Column("send_dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("attempts_send", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts_status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_status_payload", JSON_TYPE, nullable=True),
        sa.Column("requires_manual_intervention", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_edo_documents_send_dedupe_key",
        "edo_documents",
        ["send_dedupe_key"],
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_edo_documents_status", "edo_documents", ["status"], schema=SCHEMA)
    create_index_if_not_exists(
        bind,
        "ix_edo_documents_subject",
        "edo_documents",
        ["subject_type", "subject_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "edo_transitions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("edo_document_id", GUID(), sa.ForeignKey("edo_documents.id"), nullable=False),
        sa.Column("from_status", status_enum, nullable=True),
        sa.Column("to_status", status_enum, nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("actor_type", actor_enum, nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_index_if_not_exists(
        bind,
        "ix_edo_transitions_doc",
        "edo_transitions",
        ["edo_document_id", "created_at"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "edo_inbound_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("headers", JSON_TYPE, nullable=True),
        sa.Column("payload", JSON_TYPE, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", inbound_status_enum, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_edo_inbound_event_provider_id",
        "edo_inbound_events",
        ["provider_event_id"],
        schema=SCHEMA,
    )

    create_table_if_not_exists(
        bind,
        "edo_artifacts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("edo_document_id", GUID(), sa.ForeignKey("edo_documents.id"), nullable=False),
        sa.Column("artifact_type", artifact_enum, nullable=False),
        sa.Column("document_registry_id", GUID(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("provider_ref", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_index_if_not_exists(bind, "ix_edo_artifacts_doc", "edo_artifacts", ["edo_document_id"], schema=SCHEMA)

    create_table_if_not_exists(
        bind,
        "edo_outbox",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=False),
        sa.Column("dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("status", outbox_enum, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    create_unique_index_if_not_exists(
        bind,
        "uq_edo_outbox_dedupe_key",
        "edo_outbox",
        ["dedupe_key"],
        schema=SCHEMA,
    )

    if is_postgres(bind):
        if table_exists(bind, "edo_documents", schema=SCHEMA):
            if not column_exists(bind, "edo_documents", "account_id", schema=SCHEMA):
                op.add_column("edo_documents", sa.Column("account_id", GUID(), nullable=False), schema=SCHEMA)


def downgrade() -> None:
    # Keep migration idempotent; no downgrade to avoid data loss.
    pass

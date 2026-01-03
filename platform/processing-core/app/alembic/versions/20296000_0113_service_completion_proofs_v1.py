"""service completion proofs v1 tables

Revision ID: 20296000_0113_service_completion_proofs_v1
Revises: 20295010_0112_vehicle_profile_v1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.alembic.utils import (
    create_index_if_not_exists,
    create_table_if_not_exists,
    ensure_pg_enum,
    table_exists,
)
from app.db.schema import resolve_db_schema

SCHEMA = resolve_db_schema().schema

revision = "20296000_0113_service_completion_proofs_v1"
down_revision = "20295010_0112_vehicle_profile_v1"
branch_labels = None
depends_on = None

PROOF_STATUS = ["DRAFT", "SUBMITTED", "CONFIRMED", "DISPUTED", "REJECTED", "CANCELED"]
PROOF_ATTACHMENT_KIND = ["PHOTO", "INVOICE_SCAN", "ACT_PDF", "VIDEO", "OTHER"]
PROOF_DECISION = ["CONFIRM", "DISPUTE"]
PROOF_EVENT_TYPE = ["CREATED", "ATTACHED_FILE", "SUBMITTED", "CONFIRMED", "DISPUTED", "REJECTED", "RESOLVED"]
PROOF_ACTOR_TYPE = ["PARTNER", "CLIENT", "SYSTEM", "ADMIN"]


def upgrade() -> None:
    bind = op.get_bind()
    ensure_pg_enum(bind, "service_completion_proof_status", PROOF_STATUS, schema=SCHEMA)
    ensure_pg_enum(bind, "service_proof_attachment_kind", PROOF_ATTACHMENT_KIND, schema=SCHEMA)
    ensure_pg_enum(bind, "service_proof_decision", PROOF_DECISION, schema=SCHEMA)
    ensure_pg_enum(bind, "service_proof_event_type", PROOF_EVENT_TYPE, schema=SCHEMA)
    ensure_pg_enum(bind, "service_proof_actor_type", PROOF_ACTOR_TYPE, schema=SCHEMA)

    if not table_exists(bind, "service_completion_proofs", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "service_completion_proofs",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column("booking_id", sa.String(length=36), nullable=False),
                sa.Column("partner_id", sa.String(length=36), nullable=False),
                sa.Column("client_id", sa.String(length=36), nullable=False),
                sa.Column("vehicle_id", sa.String(length=36), nullable=True),
                sa.Column(
                    "status",
                    sa.Enum(*PROOF_STATUS, name="service_completion_proof_status", native_enum=False),
                    nullable=False,
                ),
                sa.Column("work_summary", sa.Text(), nullable=False),
                sa.Column("odometer_km", sa.Numeric(), nullable=True),
                sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("parts_json", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=True),
                sa.Column("labor_json", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=True),
                sa.Column("price_snapshot_json", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=False),
                sa.Column("proof_hash", sa.Text(), nullable=False),
                sa.Column("signature_json", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=False),
                sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("disputed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_service_completion_proofs_tenant", "service_completion_proofs", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_completion_proofs_booking", "service_completion_proofs", ["booking_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_completion_proofs_partner", "service_completion_proofs", ["partner_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_completion_proofs_client", "service_completion_proofs", ["client_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_completion_proofs_vehicle", "service_completion_proofs", ["vehicle_id"], schema=SCHEMA)

    if not table_exists(bind, "service_proof_attachments", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "service_proof_attachments",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column(
                    "proof_id",
                    sa.String(length=36),
                    sa.ForeignKey(f"{SCHEMA}.service_completion_proofs.id"),
                    nullable=False,
                ),
                sa.Column("attachment_id", sa.String(length=36), nullable=False),
                sa.Column(
                    "kind",
                    sa.Enum(*PROOF_ATTACHMENT_KIND, name="service_proof_attachment_kind", native_enum=False),
                    nullable=False,
                ),
                sa.Column("checksum", sa.Text(), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_service_proof_attachments_tenant", "service_proof_attachments", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_proof_attachments_proof", "service_proof_attachments", ["proof_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_proof_attachments_attachment", "service_proof_attachments", ["attachment_id"], schema=SCHEMA)

    if not table_exists(bind, "service_proof_confirmations", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "service_proof_confirmations",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column(
                    "proof_id",
                    sa.String(length=36),
                    sa.ForeignKey(f"{SCHEMA}.service_completion_proofs.id"),
                    nullable=False,
                ),
                sa.Column(
                    "decision",
                    sa.Enum(*PROOF_DECISION, name="service_proof_decision", native_enum=False),
                    nullable=False,
                ),
                sa.Column("client_comment", sa.Text(), nullable=True),
                sa.Column("client_signature_json", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=False),
                sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
            ),
        )
        create_index_if_not_exists(bind, "ix_service_proof_confirmations_tenant", "service_proof_confirmations", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_proof_confirmations_proof", "service_proof_confirmations", ["proof_id"], schema=SCHEMA)

    if not table_exists(bind, "service_proof_events", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "service_proof_events",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column(
                    "proof_id",
                    sa.String(length=36),
                    sa.ForeignKey(f"{SCHEMA}.service_completion_proofs.id"),
                    nullable=False,
                ),
                sa.Column(
                    "event_type",
                    sa.Enum(*PROOF_EVENT_TYPE, name="service_proof_event_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column(
                    "actor_type",
                    sa.Enum(*PROOF_ACTOR_TYPE, name="service_proof_actor_type", native_enum=False),
                    nullable=False,
                ),
                sa.Column("actor_id", sa.String(length=36), nullable=True),
                sa.Column("payload", sa.dialects.postgresql.JSONB(none_as_null=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_service_proof_events_tenant", "service_proof_events", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_service_proof_events_proof", "service_proof_events", ["proof_id"], schema=SCHEMA)

    if not table_exists(bind, "vehicle_service_records", schema=SCHEMA):
        create_table_if_not_exists(
            bind,
            "vehicle_service_records",
            schema=SCHEMA,
            columns=(
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.Integer(), nullable=False),
                sa.Column("vehicle_id", sa.String(length=36), nullable=False),
                sa.Column(
                    "proof_id",
                    sa.String(length=36),
                    sa.ForeignKey(f"{SCHEMA}.service_completion_proofs.id"),
                    nullable=False,
                ),
                sa.Column("work_summary", sa.Text(), nullable=False),
                sa.Column("odometer_km", sa.Numeric(), nullable=True),
                sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            ),
        )
        create_index_if_not_exists(bind, "ix_vehicle_service_records_tenant", "vehicle_service_records", ["tenant_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_vehicle_service_records_vehicle", "vehicle_service_records", ["vehicle_id"], schema=SCHEMA)
        create_index_if_not_exists(bind, "ix_vehicle_service_records_proof", "vehicle_service_records", ["proof_id"], schema=SCHEMA)


def downgrade() -> None:
    pass

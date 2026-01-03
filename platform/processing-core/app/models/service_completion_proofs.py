from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text, event, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


JSON_TYPE = JSON().with_variant(postgresql.JSONB(none_as_null=True), "postgresql")


class ServiceCompletionProofStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


class ServiceProofAttachmentKind(str, Enum):
    PHOTO = "PHOTO"
    INVOICE_SCAN = "INVOICE_SCAN"
    ACT_PDF = "ACT_PDF"
    VIDEO = "VIDEO"
    OTHER = "OTHER"


class ServiceProofDecision(str, Enum):
    CONFIRM = "CONFIRM"
    DISPUTE = "DISPUTE"


class ServiceProofEventType(str, Enum):
    CREATED = "CREATED"
    ATTACHED_FILE = "ATTACHED_FILE"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class ServiceProofActorType(str, Enum):
    PARTNER = "PARTNER"
    CLIENT = "CLIENT"
    SYSTEM = "SYSTEM"
    ADMIN = "ADMIN"


class ServiceCompletionProof(Base):
    __tablename__ = "service_completion_proofs"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)

    booking_id = Column(GUID(), nullable=False, index=True)
    partner_id = Column(GUID(), nullable=False, index=True)
    client_id = Column(GUID(), nullable=False, index=True)
    vehicle_id = Column(GUID(), nullable=True, index=True)

    status = Column(
        ExistingEnum(ServiceCompletionProofStatus, name="service_completion_proof_status"),
        nullable=False,
        default=ServiceCompletionProofStatus.DRAFT.value,
    )

    work_summary = Column(Text, nullable=False)
    odometer_km = Column(Numeric, nullable=True)
    performed_at = Column(DateTime(timezone=True), nullable=False)

    parts_json = Column(JSON_TYPE, nullable=True)
    labor_json = Column(JSON_TYPE, nullable=True)

    price_snapshot_json = Column(JSON_TYPE, nullable=False)
    proof_hash = Column(Text, nullable=False)
    signature_json = Column(JSON_TYPE, nullable=False)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    disputed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ServiceProofAttachment(Base):
    __tablename__ = "service_proof_attachments"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    proof_id = Column(GUID(), ForeignKey("service_completion_proofs.id"), nullable=False, index=True)
    attachment_id = Column(GUID(), nullable=False, index=True)
    kind = Column(
        ExistingEnum(ServiceProofAttachmentKind, name="service_proof_attachment_kind"),
        nullable=False,
    )
    checksum = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ServiceProofConfirmation(Base):
    __tablename__ = "service_proof_confirmations"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    proof_id = Column(GUID(), ForeignKey("service_completion_proofs.id"), nullable=False, index=True)
    decision = Column(ExistingEnum(ServiceProofDecision, name="service_proof_decision"), nullable=False)
    client_comment = Column(Text, nullable=True)
    client_signature_json = Column(JSON_TYPE, nullable=False)
    decision_at = Column(DateTime(timezone=True), nullable=False)


class ServiceProofEvent(Base):
    __tablename__ = "service_proof_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False, index=True)
    proof_id = Column(GUID(), ForeignKey("service_completion_proofs.id"), nullable=False, index=True)
    event_type = Column(ExistingEnum(ServiceProofEventType, name="service_proof_event_type"), nullable=False)
    actor_type = Column(ExistingEnum(ServiceProofActorType, name="service_proof_actor_type"), nullable=False)
    actor_id = Column(GUID(), nullable=True)
    payload = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


@event.listens_for(ServiceProofEvent, "before_update")
@event.listens_for(ServiceProofEvent, "before_delete")
def _block_service_proof_event_mutation(mapper, connection, target: ServiceProofEvent) -> None:
    raise ValueError("service_proof_event_immutable")


__all__ = [
    "ServiceCompletionProof",
    "ServiceCompletionProofStatus",
    "ServiceProofActorType",
    "ServiceProofAttachment",
    "ServiceProofAttachmentKind",
    "ServiceProofConfirmation",
    "ServiceProofDecision",
    "ServiceProofEvent",
    "ServiceProofEventType",
]

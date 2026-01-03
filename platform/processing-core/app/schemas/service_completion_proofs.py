from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ProofStatus = Literal[
    "DRAFT",
    "SUBMITTED",
    "CONFIRMED",
    "DISPUTED",
    "REJECTED",
    "CANCELED",
]

ProofAttachmentKind = Literal["PHOTO", "INVOICE_SCAN", "ACT_PDF", "VIDEO", "OTHER"]

ProofDecision = Literal["CONFIRM", "DISPUTE"]

ProofEventType = Literal[
    "CREATED",
    "ATTACHED_FILE",
    "SUBMITTED",
    "CONFIRMED",
    "DISPUTED",
    "REJECTED",
    "RESOLVED",
]

ProofActorType = Literal["PARTNER", "CLIENT", "SYSTEM", "ADMIN"]


class ProofCreateRequest(BaseModel):
    work_summary: str
    odometer_km: Decimal | None = None
    performed_at: datetime
    parts_json: dict | None = None
    labor_json: dict | None = None
    vehicle_id: str | None = None


class ProofAttachmentCreateRequest(BaseModel):
    attachment_id: str
    kind: ProofAttachmentKind
    checksum: str


class ProofSubmitResponse(BaseModel):
    proof_id: str
    status: ProofStatus
    proof_hash: str
    signature: dict


class ProofDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ProofDisputeRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2000)


class ProofAttachmentOut(BaseModel):
    id: str
    attachment_id: str
    kind: ProofAttachmentKind
    checksum: str
    created_at: datetime


class ProofEventOut(BaseModel):
    id: str
    event_type: ProofEventType
    actor_type: ProofActorType
    actor_id: str | None = None
    payload: dict | None = None
    created_at: datetime


class ProofOut(BaseModel):
    id: str
    booking_id: str
    partner_id: str
    client_id: str
    vehicle_id: str | None = None
    status: ProofStatus
    work_summary: str
    odometer_km: Decimal | None = None
    performed_at: datetime
    parts_json: dict | None = None
    labor_json: dict | None = None
    price_snapshot_json: dict
    proof_hash: str
    signature_json: dict
    submitted_at: datetime | None = None
    confirmed_at: datetime | None = None
    disputed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    attachments: list[ProofAttachmentOut] = Field(default_factory=list)
    events: list[ProofEventOut] = Field(default_factory=list)


class ProofConfirmationOut(BaseModel):
    id: str
    decision: ProofDecision
    client_comment: str | None = None
    client_signature_json: dict
    decision_at: datetime


class ProofAdminResolveRequest(BaseModel):
    decision: Literal["CONFIRM", "REJECT"]
    reason: str | None = Field(default=None, max_length=2000)


class ProofAdminResolveResponse(BaseModel):
    proof_id: str
    status: ProofStatus

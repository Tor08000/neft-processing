from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ContractObligationCreate(BaseModel):
    obligation_type: str
    metric: str
    threshold: Decimal
    comparison: str
    window: str | None = None
    penalty_type: str
    penalty_value: Decimal


class ContractCreateRequest(BaseModel):
    contract_number: str
    contract_type: str
    party_a_type: str
    party_a_id: str
    party_b_type: str
    party_b_id: str
    currency: str
    effective_from: datetime
    effective_to: datetime | None = None
    terms: dict
    obligations: list[ContractObligationCreate] = Field(default_factory=list)


class ContractVersionCreateRequest(BaseModel):
    terms: dict
    obligations: list[ContractObligationCreate] = Field(default_factory=list)


class ContractTerminateRequest(BaseModel):
    reason: str | None = None


class ContractEventCreateRequest(BaseModel):
    event_type: str
    occurred_at: datetime
    payload: dict


class ContractObligationResponse(BaseModel):
    id: str
    contract_id: str
    obligation_type: str
    metric: str
    threshold: Decimal
    comparison: str
    window: str | None
    penalty_type: str
    penalty_value: Decimal
    created_at: datetime


class ContractVersionResponse(BaseModel):
    id: str
    contract_id: str
    version: int
    terms: dict
    created_at: datetime
    audit_event_id: str


class ContractEventResponse(BaseModel):
    id: str
    contract_id: str
    event_type: str
    occurred_at: datetime
    payload: dict
    hash: str
    signature: str | None
    signature_alg: str | None
    signing_key_id: str | None
    signed_at: datetime | None
    audit_event_id: str


class ContractResponse(BaseModel):
    id: str
    contract_number: str
    contract_type: str
    party_a_type: str
    party_a_id: str
    party_b_type: str
    party_b_id: str
    currency: str
    effective_from: datetime
    effective_to: datetime | None
    status: str
    created_at: datetime
    audit_event_id: str
    versions: list[ContractVersionResponse] = Field(default_factory=list)
    obligations: list[ContractObligationResponse] = Field(default_factory=list)


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    total: int
    limit: int
    offset: int


class SLAEvaluateRequest(BaseModel):
    period_start: datetime
    period_end: datetime


class SLAResultResponse(BaseModel):
    id: str
    contract_id: str
    obligation_id: str
    period_start: datetime
    period_end: datetime
    measured_value: Decimal
    status: str
    created_at: datetime
    audit_event_id: str


class SLAResultsListResponse(BaseModel):
    items: list[SLAResultResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "ContractCreateRequest",
    "ContractEventCreateRequest",
    "ContractEventResponse",
    "ContractListResponse",
    "ContractObligationCreate",
    "ContractObligationResponse",
    "ContractResponse",
    "ContractTerminateRequest",
    "ContractVersionCreateRequest",
    "ContractVersionResponse",
    "SLAEvaluateRequest",
    "SLAResultResponse",
    "SLAResultsListResponse",
]

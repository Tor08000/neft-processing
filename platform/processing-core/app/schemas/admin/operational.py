from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.dispute import DisputeStatus
from app.models.refund_request import RefundRequestStatus, SettlementPolicy
from app.models.reversal import ReversalStatus


class RefundCreate(BaseModel):
    operation_id: UUID
    amount: int
    reason: Optional[str] = None
    initiator: Optional[str] = Field(default="admin")
    idempotency_key: Optional[str] = None
    settlement_closed: bool = False
    adjustment_date: Optional[date] = None


class RefundResponse(BaseModel):
    id: UUID
    operation_id: UUID
    status: RefundRequestStatus
    posting_id: Optional[UUID] = None
    settlement_policy: SettlementPolicy
    adjustment_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class ReversalCreate(BaseModel):
    operation_id: UUID
    reason: Optional[str] = None
    initiator: Optional[str] = Field(default="admin")
    idempotency_key: Optional[str] = None
    settlement_closed: bool = False
    adjustment_date: Optional[date] = None


class ReversalResponse(BaseModel):
    id: UUID
    operation_id: UUID
    status: ReversalStatus
    posting_id: Optional[UUID] = None
    settlement_policy: SettlementPolicy
    adjustment_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class DisputeOpen(BaseModel):
    operation_id: UUID
    amount: int
    fee_amount: int = 0
    initiator: Optional[str] = Field(default="admin")
    place_hold: bool = False
    idempotency_key: Optional[str] = None


class DisputeReview(BaseModel):
    initiator: Optional[str] = Field(default="admin")


class DisputeDecision(BaseModel):
    initiator: Optional[str] = Field(default="admin")
    idempotency_key: Optional[str] = None
    settlement_closed: bool = False
    adjustment_date: Optional[date] = None


class DisputeActionResponse(BaseModel):
    id: UUID
    operation_id: UUID
    status: DisputeStatus
    hold_posting_id: Optional[UUID] = None
    resolution_posting_id: Optional[UUID] = None
    adjustment_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

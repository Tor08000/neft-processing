from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.dispute import Dispute
from app.models.operation import Operation
from app.schemas.admin.operational import (
    DisputeActionResponse,
    DisputeDecision,
    DisputeOpen,
    DisputeReview,
)
from app.services.operations_scenarios.disputes import DisputeService, DisputeStateError

router = APIRouter(prefix="/disputes", tags=["admin-disputes"])


def _get_dispute_or_404(dispute_id: UUID, db: Session) -> Dispute:
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).one_or_none()
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


@router.post("/open", response_model=DisputeActionResponse)
def open_dispute(request: DisputeOpen, db: Session = Depends(get_db)) -> DisputeActionResponse:
    operation = db.query(Operation).filter(Operation.id == request.operation_id).one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    service = DisputeService(db)
    result = service.open_dispute(
        operation=operation,
        amount=request.amount,
        initiator=request.initiator,
        fee_amount=request.fee_amount,
        place_hold=request.place_hold,
        idempotency_key=request.idempotency_key or f"dispute:{uuid.uuid4()}",
    )

    dispute = result.dispute
    return DisputeActionResponse(
        id=dispute.id,
        operation_id=dispute.operation_id,
        status=dispute.status,
        hold_posting_id=result.posting_id,
        resolution_posting_id=dispute.resolution_posting_id,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


@router.post("/{dispute_id}/review", response_model=DisputeActionResponse)
def move_to_review(dispute_id: UUID, request: DisputeReview, db: Session = Depends(get_db)) -> DisputeActionResponse:
    dispute = _get_dispute_or_404(dispute_id, db)
    service = DisputeService(db)
    try:
        dispute = service.move_to_review(dispute, actor=request.initiator)
    except DisputeStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DisputeActionResponse(
        id=dispute.id,
        operation_id=dispute.operation_id,
        status=dispute.status,
        hold_posting_id=dispute.hold_posting_id,
        resolution_posting_id=dispute.resolution_posting_id,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


@router.post("/{dispute_id}/accept", response_model=DisputeActionResponse)
def accept_dispute(dispute_id: UUID, request: DisputeDecision, db: Session = Depends(get_db)) -> DisputeActionResponse:
    dispute = _get_dispute_or_404(dispute_id, db)
    operation = db.query(Operation).filter(Operation.id == dispute.operation_id).one()
    service = DisputeService(db)
    try:
        result = service.accept(
            dispute=dispute,
            operation=operation,
            initiator=request.initiator,
            idempotency_key=request.idempotency_key or f"dispute-accept:{uuid.uuid4()}",
            settlement_closed=request.settlement_closed,
            adjustment_date=request.adjustment_date,
        )
    except DisputeStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dispute = result.dispute
    return DisputeActionResponse(
        id=dispute.id,
        operation_id=dispute.operation_id,
        status=dispute.status,
        hold_posting_id=dispute.hold_posting_id,
        resolution_posting_id=dispute.resolution_posting_id,
        adjustment_id=result.adjustment_id,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


@router.post("/{dispute_id}/reject", response_model=DisputeActionResponse)
def reject_dispute(dispute_id: UUID, request: DisputeDecision, db: Session = Depends(get_db)) -> DisputeActionResponse:
    dispute = _get_dispute_or_404(dispute_id, db)
    service = DisputeService(db)
    try:
        result = service.reject(
            dispute=dispute,
            actor=request.initiator,
            idempotency_key=request.idempotency_key or f"dispute-reject:{uuid.uuid4()}",
        )
    except DisputeStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dispute = result.dispute
    return DisputeActionResponse(
        id=dispute.id,
        operation_id=dispute.operation_id,
        status=dispute.status,
        hold_posting_id=dispute.hold_posting_id,
        resolution_posting_id=dispute.resolution_posting_id,
        adjustment_id=result.adjustment_id,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


@router.post("/{dispute_id}/close", response_model=DisputeActionResponse)
def close_dispute(dispute_id: UUID, request: DisputeReview, db: Session = Depends(get_db)) -> DisputeActionResponse:
    dispute = _get_dispute_or_404(dispute_id, db)
    service = DisputeService(db)
    try:
        dispute = service.close(dispute, actor=request.initiator)
    except DisputeStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DisputeActionResponse(
        id=dispute.id,
        operation_id=dispute.operation_id,
        status=dispute.status,
        hold_posting_id=dispute.hold_posting_id,
        resolution_posting_id=dispute.resolution_posting_id,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )

from __future__ import annotations
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.intake import (
    IntakeAuthorizeRequest,
    IntakeCallbackRequest,
    IntakeRefundRequest,
    IntakeResponse,
    IntakeReversalRequest,
)
from app.services import transactions_service
from app.services.integration_hub import authorize_intake, validate_partner_request

from app.models.operation import OperationStatus

router = APIRouter(prefix="/api/v1/intake", tags=["integration"])


@router.post("/authorize", response_model=IntakeResponse)
def intake_authorize(body: IntakeAuthorizeRequest, request: Request, db: Session = Depends(get_db)) -> IntakeResponse:
    return authorize_intake(db, request, body)


@router.post("/refund", response_model=IntakeResponse)
def intake_refund(body: IntakeRefundRequest, request: Request, db: Session = Depends(get_db)) -> IntakeResponse:
    validate_partner_request(db, request, body.external_partner_id)

    operation = transactions_service.refund_operation(
        db,
        original_operation_id=body.operation_id,
        amount=body.amount or 0,
        reason=body.reason,
    )
    return IntakeResponse(
        approved=True,
        operation_id=str(operation.operation_id),
        posting_status=operation.status.value,
        risk_code=None,
        limit_code=None,
        response_code=operation.response_code,
    )


@router.post("/reversal", response_model=IntakeResponse)
def intake_reversal(body: IntakeReversalRequest, request: Request, db: Session = Depends(get_db)) -> IntakeResponse:
    validate_partner_request(db, request, body.external_partner_id)

    operation = transactions_service.reverse_operation(db, operation_id=body.operation_id, reason=body.reason)
    return IntakeResponse(
        approved=operation.status in {OperationStatus.REVERSED, OperationStatus.AUTHORIZED},
        operation_id=str(operation.operation_id),
        posting_status=operation.status.value,
        risk_code=None,
        limit_code=None,
        response_code=operation.response_code,
    )


@router.post("/callback", status_code=status.HTTP_202_ACCEPTED)
def intake_callback(body: IntakeCallbackRequest):
    # Simple sink endpoint for simulation/testing purposes.
    return {"received": True, "operation_id": body.operation_id, "status": body.status}

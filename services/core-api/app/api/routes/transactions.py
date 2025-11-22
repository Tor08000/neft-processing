from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.deps.db import get_db
from app.schemas.operations import OperationRead
from app.schemas.transactions import (
    AuthRequest,
    CaptureRequest,
    RefundRequest,
    ReversalRequest,
)


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["transactions"])


def _raise_not_implemented(endpoint: str) -> None:
    logger.warning("Endpoint %s is not implemented yet", endpoint)
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/processing/terminal-auth", response_model=OperationRead)
def terminal_auth(
    payload: AuthRequest,
    db: Session = Depends(get_db),
):
    _raise_not_implemented("terminal_auth")


@router.post("/transactions/{auth_id}/capture", response_model=OperationRead)
def capture(
    auth_id: UUID,
    payload: CaptureRequest,
    db: Session = Depends(get_db),
):
    _raise_not_implemented("capture")


@router.post("/transactions/{capture_id}/refund", response_model=OperationRead)
def refund(
    capture_id: UUID,
    payload: RefundRequest,
    db: Session = Depends(get_db),
):
    _raise_not_implemented("refund")


@router.post("/transactions/{op_id}/reversal", response_model=OperationRead)
def reversal(
    op_id: UUID,
    payload: ReversalRequest,
    db: Session = Depends(get_db),
):
    _raise_not_implemented("reversal")

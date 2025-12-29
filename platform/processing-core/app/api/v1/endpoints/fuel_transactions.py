from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelTransactionStatus
from app.schemas.fuel import (
    DeclineCode,
    FuelAuthorizeRequest,
    FuelAuthorizeResponse,
    FuelTransactionOut,
)
from app.services.audit_service import request_context_from_request
from app.services.fuel import authorize_fuel_tx, reverse_fuel_tx, settle_fuel_tx
from app.services.fuel.repository import get_fuel_transaction, list_fuel_transactions
from app.services.fuel.settlement import FuelSettlementError

router = APIRouter(
    prefix="/api/v1/fuel/transactions",
    tags=["fuel-transactions"],
)


@router.post("/authorize", response_model=FuelAuthorizeResponse)
def authorize_fuel_transaction_endpoint(
    request: Request,
    payload: FuelAuthorizeRequest,
    db: Session = Depends(get_db),
) -> FuelAuthorizeResponse:
    ctx = request_context_from_request(request)
    result = authorize_fuel_tx(db, payload=payload, request_ctx=ctx)
    return result.response


@router.post("/{transaction_id}/settle", response_model=FuelTransactionOut)
def settle_fuel_transaction_endpoint(
    request: Request,
    transaction_id: str,
    external_settlement_ref: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FuelTransactionOut:
    ctx = request_context_from_request(request)
    try:
        result = settle_fuel_tx(
            db,
            transaction_id=transaction_id,
            external_settlement_ref=external_settlement_ref,
            request_ctx=ctx,
        )
    except FuelSettlementError as exc:
        raise HTTPException(
            status_code=400,
            detail={"decline_code": exc.decline_code.value, "message": exc.message},
        ) from exc
    tx = get_fuel_transaction(db, transaction_id=result.transaction_id)
    return FuelTransactionOut.model_validate(tx)


@router.post("/{transaction_id}/reverse", response_model=FuelTransactionOut)
def reverse_fuel_transaction_endpoint(
    request: Request,
    transaction_id: str,
    external_ref: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FuelTransactionOut:
    ctx = request_context_from_request(request)
    try:
        result = reverse_fuel_tx(
            db,
            transaction_id=transaction_id,
            external_ref=external_ref,
            request_ctx=ctx,
        )
    except FuelSettlementError as exc:
        raise HTTPException(
            status_code=400,
            detail={"decline_code": exc.decline_code.value, "message": exc.message},
        ) from exc
    tx = get_fuel_transaction(db, transaction_id=result.transaction_id)
    return FuelTransactionOut.model_validate(tx)


@router.get("/{transaction_id}", response_model=FuelTransactionOut)
def get_fuel_transaction_endpoint(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> FuelTransactionOut:
    transaction = get_fuel_transaction(db, transaction_id=transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=404,
            detail={"decline_code": DeclineCode.INVALID_REQUEST.value, "message": "Not found"},
        )
    return FuelTransactionOut.model_validate(transaction)


@router.get("", response_model=list[FuelTransactionOut])
def list_fuel_transactions_endpoint(
    client_id: str | None = Query(default=None),
    card_id: str | None = Query(default=None),
    status: FuelTransactionStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FuelTransactionOut]:
    items = list_fuel_transactions(
        db,
        client_id=client_id,
        card_id=card_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [FuelTransactionOut.model_validate(item) for item in items]

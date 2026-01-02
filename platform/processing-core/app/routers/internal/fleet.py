from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelCard
from app.schemas.client_fleet import FleetTransactionListResponse, FleetTransactionOut, FleetTransactionsIngestIn
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services import fleet_service

router = APIRouter(prefix="/api/internal/fleet", tags=["internal-fleet"])


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


def _transaction_to_schema(tx) -> FleetTransactionOut:
    return FleetTransactionOut(
        id=str(tx.id),
        card_id=str(tx.card_id),
        occurred_at=tx.occurred_at,
        amount=tx.amount,
        currency=tx.currency,
        volume_liters=tx.volume_liters,
        category=tx.category,
        merchant_name=tx.merchant_name,
        station_id=tx.station_external_id,
        location=tx.location,
        external_ref=tx.external_ref,
        created_at=tx.created_at,
    )


@router.post(
    "/transactions/ingest",
    response_model=FleetTransactionListResponse,
    dependencies=[Depends(require_permission("admin:audit:*"))],
)
def ingest_transactions(
    payload: FleetTransactionsIngestIn,
    request: Request,
    principal: Principal = Depends(require_permission("admin:audit:*")),
    db: Session = Depends(get_db),
) -> FleetTransactionListResponse:
    if not payload.items:
        raise HTTPException(status_code=400, detail="empty_batch")
    first_card = db.query(FuelCard).filter(FuelCard.id == payload.items[0].card_id).one_or_none()
    if not first_card:
        raise HTTPException(status_code=404, detail="card_not_found")
    request_id, trace_id = _request_ids(request)
    items = [
        {
            "card_id": item.card_id,
            "occurred_at": item.occurred_at,
            "amount": item.amount,
            "currency": item.currency,
            "volume_liters": item.volume_liters,
            "category": item.category,
            "merchant_name": item.merchant_name,
            "station_id": item.station_id,
            "location": item.location,
            "external_ref": item.external_ref,
            "raw_payload": item.raw_payload,
        }
        for item in payload.items
    ]
    transactions = fleet_service.ingest_transactions(
        db,
        client_id=first_card.client_id,
        items=items,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetTransactionListResponse(items=[_transaction_to_schema(item) for item in transactions])


__all__ = ["router"]

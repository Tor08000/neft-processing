from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client_limits import ClientLimit
from app.models.client_operations import ClientOperation
from app.schemas.client_portal import (
    ClientOperation as ClientOperationSchema,
    ClientOperationsResponse,
    DashboardResponse,
    DashboardTotals,
    LimitItem,
    LimitsResponse,
)
from app.security.client_auth import require_client_user

router = APIRouter(prefix="/client/api/v1", tags=["client-portal"])


@router.get("/operations", response_model=ClientOperationsResponse)
async def list_operations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Фильтр по статусу"),
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort: str = Query("date_desc"),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> ClientOperationsResponse:
    if sort not in {"date_desc", "date_asc", "amount_asc", "amount_desc"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")

    query = db.query(ClientOperation).filter(ClientOperation.client_id == client_id)

    if status:
        query = query.filter(ClientOperation.status == status)
    if min_amount is not None:
        query = query.filter(ClientOperation.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(ClientOperation.amount <= max_amount)
    if date_from:
        query = query.filter(ClientOperation.performed_at >= date_from)
    if date_to:
        query = query.filter(ClientOperation.performed_at <= date_to)

    if sort == "date_asc":
        query = query.order_by(ClientOperation.performed_at.asc(), ClientOperation.id.asc())
    elif sort == "amount_asc":
        query = query.order_by(ClientOperation.amount.asc(), ClientOperation.performed_at.asc())
    elif sort == "amount_desc":
        query = query.order_by(ClientOperation.amount.desc(), ClientOperation.performed_at.desc())
    else:
        query = query.order_by(ClientOperation.performed_at.desc(), ClientOperation.id.desc())

    total = query.count()
    records: List[ClientOperation] = query.offset(offset).limit(limit).all()

    items = [
        ClientOperationSchema(
            id=str(op.id),
            date=op.performed_at,
            type=op.operation_type,
            status=op.status,
            amount=op.amount,
            currency=op.currency,
            card_ref=op.card_id,
            fuel_type=op.fuel_type,
        )
        for op in records
    ]

    return ClientOperationsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/limits", response_model=LimitsResponse)
async def list_limits(token: dict = Depends(require_client_user), db: Session = Depends(get_db)) -> LimitsResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")

    limits: List[ClientLimit] = db.query(ClientLimit).filter(ClientLimit.client_id == client_id).all()
    items = [
        LimitItem(
            id=str(limit.id),
            type=limit.limit_type,
            period=limit.limit_type,
            amount=int(limit.amount),
            used=int(limit.used_amount or 0),
            remaining=int((limit.amount or 0) - (limit.used_amount or 0)),
        )
        for limit in limits
    ]
    return LimitsResponse(items=items)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(token: dict = Depends(require_client_user), db: Session = Depends(get_db)) -> DashboardResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")

    base_query = db.query(ClientOperation).filter(ClientOperation.client_id == client_id)
    total_operations = base_query.count()
    total_amount = base_query.with_entities(func.coalesce(func.sum(ClientOperation.amount), 0)).scalar() or 0

    recent_ops_records = base_query.order_by(ClientOperation.performed_at.desc()).limit(5).all()
    recent_ops = [
        ClientOperationSchema(
            id=str(op.id),
            date=op.performed_at,
            type=op.operation_type,
            status=op.status,
            amount=op.amount,
            currency=op.currency,
            card_ref=op.card_id,
            fuel_type=op.fuel_type,
        )
        for op in recent_ops_records
    ]

    limits: List[ClientLimit] = db.query(ClientLimit).filter(ClientLimit.client_id == client_id).all()
    limit_items = [
        LimitItem(
            id=str(limit.id),
            type=limit.limit_type,
            period=limit.limit_type,
            amount=int(limit.amount),
            used=int(limit.used_amount or 0),
            remaining=int((limit.amount or 0) - (limit.used_amount or 0)),
        )
        for limit in limits
    ]

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    spending = []
    for d in dates:
        next_day = d + timedelta(days=1)
        day_sum = (
            base_query.filter(
                ClientOperation.performed_at >= datetime.combine(d, datetime.min.time()),
                ClientOperation.performed_at < datetime.combine(next_day, datetime.min.time()),
            )
            .with_entities(func.coalesce(func.sum(ClientOperation.amount), 0))
            .scalar()
            or 0
        )
        spending.append(int(day_sum))

    summary = DashboardTotals(
        total_operations=total_operations,
        total_amount=total_amount,
        period="7 дней",
        active_limits=len(limit_items),
        spending_trend=spending,
        dates=dates,
    )
    return DashboardResponse(summary=summary, recent_operations=recent_ops, limits=limit_items)

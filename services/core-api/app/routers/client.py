from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.schemas.client_portal import (
    ClientOperation,
    ClientOperationsResponse,
    DashboardResponse,
    DashboardTotals,
    LimitItem,
    LimitsResponse,
)

router = APIRouter(prefix="/client/api/v1", tags=["client-portal"])


_DEMO_OPERATIONS: List[ClientOperation] = [
    ClientOperation(
        id="op-demo-1",
        date=datetime.now(),
        type="auth",
        status="success",
        amount=18_000,
        card_ref="**** 1234",
        fuel_type="diesel",
    ),
    ClientOperation(
        id="op-demo-2",
        date=datetime.now() - timedelta(days=1, hours=2),
        type="capture",
        status="pending",
        amount=7_200,
        card_ref="**** 9876",
        fuel_type="gasoline",
    ),
    ClientOperation(
        id="op-demo-3",
        date=datetime.now() - timedelta(days=2, hours=5),
        type="refund",
        status="failed",
        amount=1_500,
        card_ref="**** 5555",
        fuel_type="diesel",
    ),
]


_DEMO_LIMITS: List[LimitItem] = [
    LimitItem(id="limit-day", type="Суточный", period="day", amount=50_000, used=18_000, remaining=32_000),
    LimitItem(id="limit-week", type="Недельный", period="week", amount=250_000, used=62_000, remaining=188_000),
    LimitItem(id="limit-month", type="Месячный", period="month", amount=1_000_000, used=240_000, remaining=760_000),
]


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
) -> ClientOperationsResponse:
    if sort not in {"date_desc", "date_asc", "amount_asc", "amount_desc"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    items = list(_DEMO_OPERATIONS)

    if status:
        items = [item for item in items if item.status == status]
    if min_amount is not None:
        items = [item for item in items if item.amount >= min_amount]
    if max_amount is not None:
        items = [item for item in items if item.amount <= max_amount]
    if date_from:
        items = [item for item in items if item.date >= date_from]
    if date_to:
        items = [item for item in items if item.date <= date_to]

    if sort == "date_asc":
        items.sort(key=lambda op: op.date)
    elif sort == "amount_asc":
        items.sort(key=lambda op: (op.amount, op.date))
    elif sort == "amount_desc":
        items.sort(key=lambda op: (-op.amount, op.date))
    else:
        items.sort(key=lambda op: (op.date, op.id), reverse=True)

    total = len(items)
    sliced = items[offset : offset + limit]
    return ClientOperationsResponse(items=sliced, total=total, limit=limit, offset=offset)


@router.get("/limits", response_model=LimitsResponse)
async def list_limits() -> LimitsResponse:
    return LimitsResponse(items=_DEMO_LIMITS)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    recent_ops = sorted(_DEMO_OPERATIONS, key=lambda op: op.date, reverse=True)[:5]
    total_amount = sum(op.amount for op in _DEMO_OPERATIONS)
    dates = [datetime.now().date() - timedelta(days=i) for i in range(6, -1, -1)]
    spending = [int(total_amount / len(dates)) for _ in dates]

    summary = DashboardTotals(
        total_operations=len(_DEMO_OPERATIONS),
        total_amount=total_amount,
        period="7 дней",
        active_limits=len(_DEMO_LIMITS),
        spending_trend=spending,
        dates=dates,
    )
    return DashboardResponse(summary=summary, recent_operations=recent_ops, limits=_DEMO_LIMITS)

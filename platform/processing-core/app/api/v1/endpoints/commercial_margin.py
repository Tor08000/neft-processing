from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.commercial_margin import MarginSortBy, SortOrder, StationMarginResponse
from app.services.commercial_margin import fetch_station_margin

router = APIRouter(prefix="/api/v1/commercial/margin", tags=["commercial"])


@router.get("/stations", response_model=StationMarginResponse)
def get_station_margins(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: MarginSortBy = Query(default=MarginSortBy.GROSS_MARGIN),
    order: SortOrder = Query(default=SortOrder.DESC),
    limit: int = Query(default=20, ge=1, le=200),
    partner_id: str | None = Query(default=None),
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StationMarginResponse:
    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else (now_day - timedelta(days=7))
    parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else now_day
    items = fetch_station_margin(
        db,
        date_from=parsed_from,
        date_to=parsed_to,
        sort_by=sort_by.value,
        order=order.value,
        limit=limit,
        partner_id=partner_id,
        risk_zone=risk_zone,
        health_status=health_status,
    )
    return StationMarginResponse(date_from=parsed_from, date_to=parsed_to, sort_by=sort_by, order=order, limit=limit, items=items)

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin.integration import (
    AzsHeatmapResponse,
    DeclineFeedItem,
    DeclineFeedResponse,
    ExternalRequestLogItem,
    ExternalRequestLogResponse,
    PartnerStatusResponse,
)
from app.services.integration_monitoring import (
    azs_stats,
    partner_status_summary,
    query_requests,
    recent_declines,
)

router = APIRouter(prefix="", tags=["admin"])


@router.get("/integration/requests", response_model=ExternalRequestLogResponse)
def list_integration_requests(
    partner_id: Optional[str] = None,
    azs_id: Optional[str] = None,
    status: Optional[str] = None,
    reason_category: Optional[str] = None,
    dt_from: Optional[datetime] = Query(None, alias="from"),
    dt_to: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ExternalRequestLogResponse:
    items, total = query_requests(
        db,
        partner_id=partner_id,
        azs_id=azs_id,
        status=status,
        reason_category=reason_category,
        dt_from=dt_from,
        dt_to=dt_to,
        limit=limit,
        offset=offset,
    )
    serialized = [ExternalRequestLogItem(**item.__dict__) for item in items]
    return ExternalRequestLogResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/integration/partners/status", response_model=PartnerStatusResponse)
def partner_status(window_minutes: int = Query(15, ge=1, le=120), db: Session = Depends(get_db)) -> PartnerStatusResponse:
    items = partner_status_summary(db, window_minutes=window_minutes)
    return PartnerStatusResponse(items=items)


@router.get("/integration/azs/heatmap", response_model=AzsHeatmapResponse)
def azs_heatmap(
    window_minutes: int = Query(15, ge=1, le=120),
    partner_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> AzsHeatmapResponse:
    items = azs_stats(db, window_minutes=window_minutes, partner_id=partner_id)
    return AzsHeatmapResponse(items=items)


@router.get("/integration/declines/recent", response_model=DeclineFeedResponse)
def recent_declines_feed(
    since: Optional[datetime] = None,
    partner_id: Optional[str] = None,
    reason_category: Optional[str] = None,
    db: Session = Depends(get_db),
) -> DeclineFeedResponse:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(minutes=5)
    items = recent_declines(db, since=since, partner_id=partner_id, reason_category=reason_category)
    serialized = [DeclineFeedItem(**item.__dict__) for item in items]
    return DeclineFeedResponse(items=serialized)


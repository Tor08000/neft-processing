from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.commercial_price_recommendations import (
    PriceRecommendationListResponse,
    PriceRecommendationStatusResponse,
    RecommendationAction,
    RecommendationStatus,
)
from app.services.commercial_price_recommendations import (
    get_station_price_recommendations,
    list_price_recommendations,
    update_recommendation_status,
)

router = APIRouter(prefix="/api/v1/commercial/recommendations/prices", tags=["commercial"])
admin_router = APIRouter(prefix="/api/v1/admin/commercial/recommendations", tags=["commercial-admin"])


@router.get("", response_model=PriceRecommendationListResponse)
def get_price_recommendations(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    status: RecommendationStatus | None = Query(default=None),
    action: RecommendationAction | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    risk_zone: str | None = Query(default=None),
    health_status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PriceRecommendationListResponse:
    now_day = datetime.now(tz=timezone.utc).date()
    parsed_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else (now_day - timedelta(days=7))
    parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else now_day
    items = list_price_recommendations(
        db,
        date_from=parsed_from,
        date_to=parsed_to,
        status=status.value if status else None,
        action=action.value if action else None,
        min_confidence=min_confidence,
        risk_zone=risk_zone,
        health_status=health_status,
        limit=limit,
    )
    return PriceRecommendationListResponse(date_from=parsed_from, date_to=parsed_to, limit=limit, items=items)


@router.get("/stations/{station_id}", response_model=PriceRecommendationListResponse)
def get_station_recommendations(
    station_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PriceRecommendationListResponse:
    items = get_station_price_recommendations(db, station_id=station_id, limit=limit)
    now_day = datetime.now(tz=timezone.utc).date()
    return PriceRecommendationListResponse(
        date_from=now_day - timedelta(days=30),
        date_to=now_day,
        limit=limit,
        items=items,
    )


@admin_router.post("/{recommendation_id}/accept", response_model=PriceRecommendationStatusResponse)
def accept_recommendation(
    recommendation_id: str,
    _token: dict = Depends(require_admin_user),
) -> PriceRecommendationStatusResponse:
    if not update_recommendation_status(recommendation_id, RecommendationStatus.ACCEPTED.value):
        raise HTTPException(status_code=503, detail="recommendations_storage_unavailable")
    return PriceRecommendationStatusResponse(id=recommendation_id, status=RecommendationStatus.ACCEPTED)


@admin_router.post("/{recommendation_id}/reject", response_model=PriceRecommendationStatusResponse)
def reject_recommendation(
    recommendation_id: str,
    _token: dict = Depends(require_admin_user),
) -> PriceRecommendationStatusResponse:
    if not update_recommendation_status(recommendation_id, RecommendationStatus.REJECTED.value):
        raise HTTPException(status_code=503, detail="recommendations_storage_unavailable")
    return PriceRecommendationStatusResponse(id=recommendation_id, status=RecommendationStatus.REJECTED)

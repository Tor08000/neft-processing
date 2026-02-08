from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from redis import Redis
from sqlalchemy.orm import Session

from app.api.dependencies.redis import get_redis
from app.db import get_db
from app.schemas.marketplace.recommendations_v1 import RecommendationResponse, RecommendationWhyResponse
from app.security.client_auth import require_client_user
from app.services.marketplace_recommendations_service import MarketplaceRecommendationsService

router = APIRouter(prefix="/v1/marketplace/client/recommendations", tags=["client-portal-v1"])


def _extract_subscription_codes(token: dict) -> list[str]:
    if not token:
        return []
    codes = token.get("subscription_codes")
    if isinstance(codes, list):
        return [str(item) for item in codes]
    subscription = token.get("subscription") or {}
    code = subscription.get("code") or subscription.get("plan_code")
    if code:
        return [str(code)]
    entitlements = token.get("entitlements_snapshot") or {}
    subscription_payload = entitlements.get("subscription") or {}
    ent_code = subscription_payload.get("code") or subscription_payload.get("plan_code")
    if ent_code:
        return [str(ent_code)]
    return []


def _extract_geo(token: dict) -> str | None:
    if not token:
        return None
    return token.get("region_code") or token.get("geo")


@router.get("", response_model=RecommendationResponse)
def list_recommendations(
    limit: int = Query(12, ge=1, le=50),
    mode: str = Query("default"),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RecommendationResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    _ = mode
    service = MarketplaceRecommendationsService(db, redis=redis)
    return service.list_recommendations(
        tenant_id=token.get("tenant_id"),
        client_id=str(client_id),
        limit=limit,
        subscription_codes=_extract_subscription_codes(token),
        geo=_extract_geo(token),
    )


@router.get("/why", response_model=RecommendationWhyResponse)
def explain_recommendation(
    offer_id: str = Query(...),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RecommendationWhyResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service = MarketplaceRecommendationsService(db, redis=redis)
    payload = service.explain_why(
        tenant_id=token.get("tenant_id"),
        client_id=str(client_id),
        offer_id=offer_id,
        subscription_codes=_extract_subscription_codes(token),
        geo=_extract_geo(token),
    )
    if not payload:
        raise HTTPException(status_code=404, detail="offer_not_found")
    return RecommendationWhyResponse(**payload)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_sponsored import SponsoredCampaignStatus
from app.schemas.marketplace.sponsored import (
    SponsoredCampaignCreate,
    SponsoredCampaignListResponse,
    SponsoredCampaignOut,
    SponsoredCampaignStatsOut,
    SponsoredCampaignStatusUpdate,
    SponsoredCampaignUpdate,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_sponsored_service import MarketplaceSponsoredService

router = APIRouter(prefix="/partner/marketplace/sponsored", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _campaign_out(campaign) -> SponsoredCampaignOut:
    return SponsoredCampaignOut(
        id=str(campaign.id),
        tenant_id=str(campaign.tenant_id),
        partner_id=str(campaign.partner_id),
        title=campaign.title,
        status=campaign.status.value if hasattr(campaign.status, "value") else campaign.status,
        objective=campaign.objective.value if hasattr(campaign.objective, "value") else campaign.objective,
        currency=campaign.currency,
        targeting=campaign.targeting,
        scope=campaign.scope,
        bid=campaign.bid,
        daily_cap=campaign.daily_cap,
        total_budget=campaign.total_budget,
        spent_budget=campaign.spent_budget,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.get("/campaigns", response_model=SponsoredCampaignListResponse)
def list_campaigns(
    request: Request,
    status: SponsoredCampaignStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    items, total = service.list_campaigns(partner_id=partner_id, status=status, limit=limit, offset=offset)
    return SponsoredCampaignListResponse(
        items=[_campaign_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/campaigns", response_model=SponsoredCampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: SponsoredCampaignCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignOut:
    partner_id = _ensure_partner_context(principal)
    tenant_id = principal.raw_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_required")
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    campaign = service.create_campaign(
        tenant_id=str(tenant_id),
        partner_id=partner_id,
        payload=payload.dict(),
    )
    db.commit()
    return _campaign_out(campaign)


@router.get("/campaigns/{campaign_id}", response_model=SponsoredCampaignOut)
def get_campaign(
    campaign_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    campaign = service.get_campaign(campaign_id)
    if not campaign or str(campaign.partner_id) != partner_id:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return _campaign_out(campaign)


@router.patch("/campaigns/{campaign_id}", response_model=SponsoredCampaignOut)
def update_campaign(
    campaign_id: str,
    payload: SponsoredCampaignUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    campaign = service.get_campaign(campaign_id)
    if not campaign or str(campaign.partner_id) != partner_id:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    campaign = service.update_campaign(campaign=campaign, payload=payload.dict(exclude_unset=True))
    db.commit()
    return _campaign_out(campaign)


@router.patch("/campaigns/{campaign_id}/status", response_model=SponsoredCampaignOut)
def update_campaign_status(
    campaign_id: str,
    payload: SponsoredCampaignStatusUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    campaign = service.get_campaign(campaign_id)
    if not campaign or str(campaign.partner_id) != partner_id:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    campaign = service.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus(payload.status), reason=payload.reason)
    db.commit()
    return _campaign_out(campaign)


@router.get("/campaigns/{campaign_id}/stats", response_model=SponsoredCampaignStatsOut)
def get_campaign_stats(
    campaign_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:sponsored:*")),
    db: Session = Depends(get_db),
) -> SponsoredCampaignStatsOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )
    campaign = service.get_campaign(campaign_id)
    if not campaign or str(campaign.partner_id) != partner_id:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    stats = service.campaign_stats(campaign_id=campaign_id)
    return SponsoredCampaignStatsOut(**stats)

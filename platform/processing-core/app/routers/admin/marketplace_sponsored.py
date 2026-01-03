from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_sponsored import SponsoredCampaignStatus
from app.schemas.marketplace.sponsored import (
    SponsoredCampaignListResponse,
    SponsoredCampaignOut,
    SponsoredCampaignStatusUpdate,
    SponsoredChargeRequest,
    SponsoredLedgerEntryOut,
    SponsoredRefundRequest,
)
from app.services.audit_service import request_context_from_request
from app.services.marketplace_sponsored_service import MarketplaceSponsoredService

router = APIRouter(tags=["admin"])


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


def _ledger_out(entry) -> SponsoredLedgerEntryOut:
    return SponsoredLedgerEntryOut(
        id=str(entry.id),
        campaign_id=str(entry.campaign_id),
        partner_id=str(entry.partner_id),
        spend_type=entry.spend_type.value if hasattr(entry.spend_type, "value") else entry.spend_type,
        amount=entry.amount,
        currency=entry.currency,
        ref_type=entry.ref_type,
        ref_id=str(entry.ref_id),
        direction=entry.direction.value if hasattr(entry.direction, "value") else entry.direction,
        reversal_of=str(entry.reversal_of) if entry.reversal_of else None,
        created_at=entry.created_at,
    )


@router.get("/marketplace/sponsored/campaigns", response_model=SponsoredCampaignListResponse)
def list_campaigns(
    request: Request,
    partner_id: str | None = Query(None),
    tenant_id: str | None = Query(None),
    status: SponsoredCampaignStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SponsoredCampaignListResponse:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    items, total = service.list_campaigns(
        tenant_id=tenant_id,
        partner_id=partner_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return SponsoredCampaignListResponse(
        items=[_campaign_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/marketplace/sponsored/campaigns/{campaign_id}/status", response_model=SponsoredCampaignOut)
def update_campaign_status(
    campaign_id: str,
    payload: SponsoredCampaignStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> SponsoredCampaignOut:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    campaign = service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    campaign = service.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus(payload.status), reason=payload.reason)
    db.commit()
    return _campaign_out(campaign)


@router.post("/marketplace/sponsored/partners/{partner_id}/pause", response_model=int)
def pause_partner_campaigns(
    partner_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    items, _ = service.list_campaigns(partner_id=partner_id, limit=1000, offset=0)
    for campaign in items:
        service.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus.PAUSED, reason="admin_kill_switch")
    db.commit()
    return len(items)


@router.post("/marketplace/sponsored/partners/{partner_id}/resume", response_model=int)
def resume_partner_campaigns(
    partner_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    items, _ = service.list_campaigns(partner_id=partner_id, limit=1000, offset=0)
    for campaign in items:
        if campaign.status == SponsoredCampaignStatus.PAUSED:
            service.set_campaign_status(campaign=campaign, status=SponsoredCampaignStatus.ACTIVE, reason="admin_resume")
    db.commit()
    return len(items)


@router.post("/marketplace/sponsored/charges/paid", response_model=SponsoredLedgerEntryOut | None)
def charge_order_paid(
    payload: SponsoredChargeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SponsoredLedgerEntryOut | None:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    entry = service.charge_cpa_for_order_paid(
        order_id=payload.order_id,
        paid_amount=payload.paid_amount,
        currency=payload.paid_currency,
    )
    db.commit()
    if entry is None:
        return None
    return _ledger_out(entry)


@router.post("/marketplace/sponsored/charges/refund", response_model=SponsoredLedgerEntryOut | None)
def reverse_order_refund(
    payload: SponsoredRefundRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SponsoredLedgerEntryOut | None:
    service = MarketplaceSponsoredService(
        db,
        request_ctx=request_context_from_request(request),
    )
    entry = service.reverse_cpa_for_refund(
        order_id=payload.order_id,
        refunded_amount=payload.refunded_amount,
        paid_amount=payload.paid_amount,
        currency=payload.currency,
    )
    db.commit()
    if entry is None:
        return None
    return _ledger_out(entry)

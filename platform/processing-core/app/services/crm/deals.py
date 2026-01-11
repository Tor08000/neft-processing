from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMDeal, CRMDealEvent, CRMDealEventType
from app.schemas.crm import CRMDealCreate, CRMDealUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def create_deal(
    db: Session,
    *,
    payload: CRMDealCreate,
    request_ctx: RequestContext | None,
) -> CRMDeal:
    deal = CRMDeal(
        tenant_id=payload.tenant_id,
        lead_id=payload.lead_id,
        client_id=payload.client_id,
        stage=payload.stage,
        value_amount=payload.value_amount,
        currency=payload.currency,
        probability=payload.probability,
        next_step=payload.next_step,
        owner_id=payload.owner_id,
    )
    deal = repository.add_deal(db, deal)
    repository.add_deal_event(
        db,
        CRMDealEvent(
            deal_id=deal.id,
            event_type=CRMDealEventType.STAGE_CHANGED,
            payload={"stage": deal.stage.value},
            actor_id=request_ctx.actor_id if request_ctx else None,
        ),
    )
    return deal


def update_deal_stage(
    db: Session,
    *,
    deal: CRMDeal,
    payload: CRMDealUpdate,
    request_ctx: RequestContext | None,
) -> CRMDeal:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deal, field, value)
    deal = repository.update_deal(db, deal)
    if payload.stage:
        repository.add_deal_event(
            db,
            CRMDealEvent(
                deal_id=deal.id,
                event_type=CRMDealEventType.STAGE_CHANGED,
                payload={"stage": deal.stage.value},
                actor_id=request_ctx.actor_id if request_ctx else None,
            ),
        )
        events.audit_event(
            db,
            event_type=events.CRM_DEAL_STAGE_CHANGED,
            entity_type="crm_deal",
            entity_id=str(deal.id),
            payload={"stage": deal.stage.value},
            request_ctx=request_ctx,
        )
    return deal


__all__ = ["create_deal", "update_deal_stage"]

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMDeal, CRMPipelineStage
from app.schemas.deals import DealCreate, DealListOut, DealOut, DealUpdate, MarkLostIn, MarkWonIn, MoveStageIn
from app.services.audit_service import audit_create, audit_update

router = APIRouter(prefix="/deals", tags=["crm-deals"])


@router.get("", response_model=DealListOut)
def list_deals(
    pipeline_id: str | None = None,
    stage_id: str | None = None,
    status: str | None = None,
    owner_user_id: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    query = select(CRMDeal).where(CRMDeal.tenant_id == auth.tenant_id)
    if pipeline_id:
        query = query.where(CRMDeal.pipeline_id == pipeline_id)
    if stage_id:
        query = query.where(CRMDeal.stage_id == stage_id)
    if status:
        query = query.where(CRMDeal.status == status)
    if owner_user_id:
        query = query.where(CRMDeal.owner_user_id == owner_user_id)
    if search:
        query = query.where(or_(CRMDeal.title.ilike(f"%{search}%"), CRMDeal.close_reason.ilike(f"%{search}%")))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMDeal.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return DealListOut(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=DealOut)
def create_deal(payload: DealCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    stage = db.get(CRMPipelineStage, payload.stage_id)
    if not stage or stage.tenant_id != auth.tenant_id or stage.pipeline_id != payload.pipeline_id:
        raise HTTPException(status_code=400, detail="Stage does not belong to tenant pipeline")
    model = CRMDeal(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(model)
    db.flush()
    audit_create(db, auth.tenant_id, "deal", model.id, auth.actor, payload.model_dump())
    db.commit()
    db.refresh(model)
    return model


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(deal_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMDeal, deal_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    return model


@router.patch("/{deal_id}", response_model=DealOut)
def patch_deal(deal_id: str, payload: DealUpdate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMDeal, deal_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    before = DealOut.model_validate(model).model_dump(mode="json")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(model, k, v)
    after = DealOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "deal", model.id, auth.actor, before, after)
    db.commit()
    db.refresh(model)
    return model


@router.post("/{deal_id}/move-stage", response_model=DealOut)
def move_stage(deal_id: str, payload: MoveStageIn, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMDeal, deal_id)
    stage = db.get(CRMPipelineStage, payload.stage_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    if not stage or stage.tenant_id != auth.tenant_id or stage.pipeline_id != model.pipeline_id:
        raise HTTPException(status_code=400, detail="Stage does not belong to deal pipeline")
    before = DealOut.model_validate(model).model_dump(mode="json")
    model.stage_id = payload.stage_id
    after = DealOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "deal", model.id, auth.actor, before, after, action="stage_change")
    db.commit()
    db.refresh(model)
    return model


@router.post("/{deal_id}/mark-won", response_model=DealOut)
def mark_won(deal_id: str, payload: MarkWonIn, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMDeal, deal_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    before = DealOut.model_validate(model).model_dump(mode="json")
    model.status = "won"
    if payload.amount is not None:
        model.amount = payload.amount
    model.close_reason = payload.close_reason
    after = DealOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "deal", model.id, auth.actor, before, after, action="won")
    db.commit()
    db.refresh(model)
    return model


@router.post("/{deal_id}/mark-lost", response_model=DealOut)
def mark_lost(deal_id: str, payload: MarkLostIn, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = db.get(CRMDeal, deal_id)
    if not model or model.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Deal not found")
    before = DealOut.model_validate(model).model_dump(mode="json")
    model.status = "lost"
    model.close_reason = payload.close_reason
    after = DealOut.model_validate(model).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "deal", model.id, auth.actor, before, after, action="lost")
    db.commit()
    db.refresh(model)
    return model

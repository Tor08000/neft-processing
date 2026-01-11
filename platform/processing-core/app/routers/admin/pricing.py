from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.pricing import PriceSchedule, PriceScheduleStatus, PriceVersion, PriceVersionItem
from app.schemas.pricing import (
    PriceRollbackIn,
    PriceScheduleActivateNow,
    PriceScheduleCreate,
    PriceScheduleOut,
    PriceVersionCreate,
    PriceVersionItemIn,
    PriceVersionItemOut,
    PriceVersionOut,
)
from app.services.pricing_versions import (
    activate_schedule_now,
    add_price_version_item,
    cancel_schedule,
    create_price_version,
    create_schedule,
    list_price_versions,
    publish_price_version,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/versions", response_model=list[PriceVersionOut])
def list_versions(db: Session = Depends(get_db)) -> list[PriceVersionOut]:
    items = list_price_versions(db)
    return [PriceVersionOut.model_validate(item) for item in items]


@router.post("/versions", response_model=PriceVersionOut, status_code=status.HTTP_201_CREATED)
def create_version(payload: PriceVersionCreate, db: Session = Depends(get_db)) -> PriceVersionOut:
    version = create_price_version(db, name=payload.name, notes=payload.notes)
    return PriceVersionOut.model_validate(version)


@router.post("/versions/{price_version_id}/publish", response_model=PriceVersionOut)
def publish_version(price_version_id: str, db: Session = Depends(get_db)) -> PriceVersionOut:
    version = publish_price_version(db, price_version_id=price_version_id)
    return PriceVersionOut.model_validate(version)


@router.post("/versions/{price_version_id}/items", response_model=PriceVersionItemOut)
def upsert_item(
    price_version_id: str,
    payload: PriceVersionItemIn,
    db: Session = Depends(get_db),
) -> PriceVersionItemOut:
    item = add_price_version_item(
        db,
        price_version_id=price_version_id,
        plan_code=payload.plan_code,
        billing_period=payload.billing_period,
        currency=payload.currency,
        base_price=payload.base_price,
        setup_fee=payload.setup_fee,
        meta=payload.meta,
    )
    return PriceVersionItemOut.model_validate(item)


@router.get("/versions/{price_version_id}/items", response_model=list[PriceVersionItemOut])
def list_items(price_version_id: str, db: Session = Depends(get_db)) -> list[PriceVersionItemOut]:
    items = db.query(PriceVersionItem).filter(PriceVersionItem.price_version_id == price_version_id).all()
    return [PriceVersionItemOut.model_validate(item) for item in items]


@router.post("/schedules", response_model=PriceScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule_endpoint(payload: PriceScheduleCreate, db: Session = Depends(get_db)) -> PriceScheduleOut:
    schedule = create_schedule(
        db,
        price_version_id=payload.price_version_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        priority=payload.priority,
    )
    return PriceScheduleOut.model_validate(schedule)


@router.post("/schedules/{schedule_id}/activate_now", response_model=PriceScheduleOut)
def activate_schedule_endpoint(
    schedule_id: str,
    payload: PriceScheduleActivateNow,
    db: Session = Depends(get_db),
) -> PriceScheduleOut:
    if payload.effective_from:
        schedule = db.get(PriceSchedule, schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="price_schedule_not_found")
        schedule.effective_from = payload.effective_from
        schedule.status = PriceScheduleStatus.ACTIVE
        db.commit()
        db.refresh(schedule)
        return PriceScheduleOut.model_validate(schedule)
    schedule = activate_schedule_now(db, schedule_id=schedule_id)
    return PriceScheduleOut.model_validate(schedule)


@router.post("/versions/{price_version_id}/rollback", response_model=PriceScheduleOut)
def rollback_version(
    price_version_id: str,
    payload: PriceRollbackIn,
    db: Session = Depends(get_db),
) -> PriceScheduleOut:
    version = db.get(PriceVersion, price_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="price_version_not_found")
    schedule = cancel_schedule(db, schedule_id=payload.schedule_id)
    return PriceScheduleOut.model_validate(schedule)


__all__ = ["router"]

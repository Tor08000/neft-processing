from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.merchant import Merchant
from app.schemas.merchants import (
    MerchantCreate,
    MerchantSchema,
    MerchantUpdate,
    MerchantsPage,
)

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("", response_model=MerchantsPage)
def list_merchants(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> MerchantsPage:
    query = db.query(Merchant)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return MerchantsPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=MerchantSchema)
def create_merchant(
    payload: MerchantCreate = Body(...), db: Session = Depends(get_db)
) -> MerchantSchema:
    merchant = Merchant(id=payload.id, name=payload.name, status=payload.status)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("/{merchant_id}", response_model=MerchantSchema)
def get_merchant(merchant_id: str, db: Session = Depends(get_db)) -> MerchantSchema:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="merchant not found")
    return merchant


@router.patch("/{merchant_id}", response_model=MerchantSchema)
def update_merchant(
    merchant_id: str, payload: MerchantUpdate = Body(...), db: Session = Depends(get_db)
) -> MerchantSchema:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="merchant not found")

    if payload.name is not None:
        merchant.name = payload.name
    if payload.status is not None:
        merchant.status = payload.status

    db.commit()
    db.refresh(merchant)
    return merchant


@router.delete("/{merchant_id}", response_model=MerchantSchema)
def delete_merchant(merchant_id: str, db: Session = Depends(get_db)) -> MerchantSchema:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="merchant not found")

    merchant.status = "DELETED"
    db.commit()
    db.refresh(merchant)
    return merchant

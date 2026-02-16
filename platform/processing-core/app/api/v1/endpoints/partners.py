from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.partner import Partner
from app.schemas.partners import PartnerCreate, PartnerSchema, PartnerUpdate

router = APIRouter(prefix="/api/v1/partners", tags=["partners"])


@router.get("", response_model=list[PartnerSchema])
def list_partners(db: Session = Depends(get_db)) -> list[PartnerSchema]:
    return db.query(Partner).order_by(Partner.created_at.desc()).all()


@router.post("", response_model=PartnerSchema, status_code=status.HTTP_201_CREATED)
def create_partner(body: PartnerCreate, db: Session = Depends(get_db)) -> PartnerSchema:
    existing = db.query(Partner).filter(Partner.id == body.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="partner_exists")
    partner = Partner(
        id=body.id,
        name=body.name,
        type=body.type,
        status=body.status,
        allowed_ips=body.allowed_ips,
        token=body.token,
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


@router.get("/{partner_id}", response_model=PartnerSchema)
def get_partner(partner_id: str, db: Session = Depends(get_db)) -> PartnerSchema:
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_found")
    return partner


@router.put("/{partner_id}", response_model=PartnerSchema)
def update_partner(partner_id: str, body: PartnerUpdate, db: Session = Depends(get_db)) -> PartnerSchema:
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(partner, field, value)

    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


@router.delete("/{partner_id}", status_code=status.HTTP_200_OK)
def disable_partner(partner_id: str, db: Session = Depends(get_db)) -> None:
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_found")
    partner.status = "disabled"
    db.add(partner)
    db.commit()

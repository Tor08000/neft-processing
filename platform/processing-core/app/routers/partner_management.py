from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.partner import Partner
from app.models.partner_management import PartnerLocation, PartnerTerms, PartnerUserRole
from app.schemas.partner_management import (
    PartnerLocationCreate,
    PartnerLocationOut,
    PartnerLocationUpdate,
    PartnerMePatch,
    PartnerOut,
    PartnerTermsOut,
)

router = APIRouter(prefix="/partner", tags=["partner-management-v1"])


def _user_id_from_token(token: dict) -> str:
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user_context")
    return user_id


def get_current_partner(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> Partner:
    user_id = _user_id_from_token(token)
    link = db.query(PartnerUserRole).filter(PartnerUserRole.user_id == user_id).first()
    if not link:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    partner = db.get(Partner, link.partner_id)
    if not partner:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    if partner.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="partner_inactive")
    return partner


@router.get("/me", response_model=PartnerOut)
def partner_me(partner: Partner = Depends(get_current_partner)) -> PartnerOut:
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.patch("/me", response_model=PartnerOut)
def patch_partner_me(
    payload: PartnerMePatch,
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> PartnerOut:
    if payload.contacts is not None:
        partner.contacts = payload.contacts
    if payload.brand_name is not None:
        partner.brand_name = payload.brand_name
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.get("/locations", response_model=list[PartnerLocationOut])
def list_locations(
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> list[PartnerLocationOut]:
    rows = db.query(PartnerLocation).filter(PartnerLocation.partner_id == partner.id).all()
    return [PartnerLocationOut.model_validate(row, from_attributes=True) for row in rows]


@router.post("/locations", response_model=PartnerLocationOut, status_code=201)
def create_location(
    payload: PartnerLocationCreate,
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    row = PartnerLocation(partner_id=partner.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerLocationOut.model_validate(row, from_attributes=True)


@router.patch("/locations/{location_id}", response_model=PartnerLocationOut)
def patch_location(
    location_id: str,
    payload: PartnerLocationUpdate,
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    row = db.get(PartnerLocation, location_id)
    if not row or str(row.partner_id) != str(partner.id):
        raise HTTPException(status_code=404, detail="location_not_found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerLocationOut.model_validate(row, from_attributes=True)


@router.delete("/locations/{location_id}", response_model=PartnerLocationOut)
def delete_location(
    location_id: str,
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    row = db.get(PartnerLocation, location_id)
    if not row or str(row.partner_id) != str(partner.id):
        raise HTTPException(status_code=404, detail="location_not_found")
    row.status = "INACTIVE"
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerLocationOut.model_validate(row, from_attributes=True)


@router.get("/terms", response_model=PartnerTermsOut)
def get_terms(
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> PartnerTermsOut:
    active = (
        db.query(PartnerTerms)
        .filter(PartnerTerms.partner_id == partner.id, PartnerTerms.status == "ACTIVE")
        .order_by(PartnerTerms.version.desc())
        .first()
    )
    row = active or (
        db.query(PartnerTerms)
        .filter(PartnerTerms.partner_id == partner.id)
        .order_by(PartnerTerms.version.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="terms_not_found")
    return PartnerTermsOut.model_validate(row, from_attributes=True)

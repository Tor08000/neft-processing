from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.types import new_uuid_str
from app.models.partner import Partner
from app.models.partner_management import PartnerTerms, PartnerUserRole
from app.schemas.partner_management import (
    PartnerCreate,
    PartnerOut,
    PartnerUpdate,
    PartnerUserRoleCreate,
    PartnerUserRoleOut,
)

router = APIRouter(prefix="/partners", tags=["admin-partners-v1"])


@router.post("", response_model=PartnerOut, status_code=201)
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):
    owner_user_id = payload.owner_user_id or payload.owner_user_email
    if not owner_user_id:
        raise HTTPException(status_code=400, detail="owner_user_required")
    if db.query(Partner).filter(Partner.code == payload.code).first():
        raise HTTPException(status_code=409, detail="partner_code_exists")

    partner = Partner(
        code=payload.code,
        legal_name=payload.legal_name,
        brand_name=payload.brand_name,
        partner_type=payload.partner_type,
        inn=payload.inn,
        ogrn=payload.ogrn,
        status=payload.status,
        contacts=payload.contacts,
    )
    db.add(partner)
    db.flush()

    db.add(
        PartnerTerms(
            partner_id=partner.id,
            version=1,
            status="DRAFT",
            terms={"commission": {}, "settlement_delay_days": None, "limits": {}, "sla": {}},
        )
    )
    db.add(
        PartnerUserRole(
            id=new_uuid_str(),
            partner_id=partner.id,
            user_id=owner_user_id,
            roles=["PARTNER_OWNER"],
        )
    )
    db.commit()
    db.refresh(partner)
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.get("", response_model=list[PartnerOut])
def list_partners(
    status: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[PartnerOut]:
    query = db.query(Partner)
    if status:
        query = query.filter(Partner.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Partner.code.ilike(like), Partner.legal_name.ilike(like), Partner.brand_name.ilike(like)))
    rows = query.order_by(Partner.created_at.desc()).all()
    return [PartnerOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/{partner_id}", response_model=PartnerOut)
def get_partner(partner_id: str, db: Session = Depends(get_db)) -> PartnerOut:
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="partner_not_found")
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.patch("/{partner_id}", response_model=PartnerOut)
def patch_partner(partner_id: str, payload: PartnerUpdate, db: Session = Depends(get_db)) -> PartnerOut:
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="partner_not_found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(partner, key, value)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.post("/{partner_id}/users", response_model=PartnerUserRoleOut, status_code=201)
def add_partner_user(partner_id: str, payload: PartnerUserRoleCreate, db: Session = Depends(get_db)) -> PartnerUserRoleOut:
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="partner_not_found")
    user_id = payload.user_id or payload.email
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    row = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner_id, PartnerUserRole.user_id == user_id).first()
    if row:
        row.roles = payload.roles
    else:
        row = PartnerUserRole(partner_id=partner_id, user_id=user_id, roles=payload.roles)
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerUserRoleOut(user_id=str(row.user_id), roles=list(row.roles or []), created_at=row.created_at)


@router.get("/{partner_id}/users", response_model=list[PartnerUserRoleOut])
def list_partner_users(partner_id: str, db: Session = Depends(get_db)) -> list[PartnerUserRoleOut]:
    rows = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner_id).all()
    return [PartnerUserRoleOut(user_id=str(row.user_id), roles=list(row.roles or []), created_at=row.created_at) for row in rows]


@router.delete("/{partner_id}/users/{user_id}", status_code=200)
def delete_partner_user(partner_id: str, user_id: str, db: Session = Depends(get_db)) -> None:
    row = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner_id, PartnerUserRole.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="partner_user_not_found")
    db.delete(row)
    db.commit()
    return None

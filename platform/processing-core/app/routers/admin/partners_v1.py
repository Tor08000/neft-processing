from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.types import new_uuid_str
from app.models.partner import Partner
from app.models.partner_management import PartnerTerms, PartnerUserRole
from app.schemas.partner_management import (
    PartnerCreate,
    PartnerListOut,
    PartnerOut,
    PartnerUpdate,
    PartnerUserRoleCreate,
    PartnerUserRoleOut,
)

router = APIRouter(prefix="/partners", tags=["admin-partners-v1"])


@router.post("", response_model=PartnerOut, status_code=201)
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):
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
            terms={},
        )
    )

    owner_user_id = payload.owner_user_id or payload.owner_user_email
    if owner_user_id:
        row = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner.id, PartnerUserRole.user_id == owner_user_id).first()
        if row:
            current_roles = set(row.roles or [])
            current_roles.add("PARTNER_OWNER")
            row.roles = sorted(current_roles)
        else:
            row = PartnerUserRole(
                id=new_uuid_str(),
                partner_id=partner.id,
                user_id=owner_user_id,
                roles=["PARTNER_OWNER"],
            )
        db.add(row)

    db.commit()
    db.refresh(partner)
    return PartnerOut.model_validate(partner, from_attributes=True)


@router.get("", response_model=PartnerListOut)
def list_partners(
    status: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PartnerListOut:
    query = db.query(Partner)
    if status:
        query = query.filter(Partner.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Partner.code.ilike(like), Partner.legal_name.ilike(like), Partner.brand_name.ilike(like)))

    total = query.with_entities(func.count(Partner.id)).scalar() or 0
    rows = query.order_by(Partner.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PartnerListOut(
        items=[PartnerOut.model_validate(row, from_attributes=True) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


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

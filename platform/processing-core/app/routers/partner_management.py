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
    PartnerMeOut,
    PartnerMePatch,
    PartnerOut,
    PartnerTermsOut,
    PartnerUserRoleOut,
    PartnerUserRoleSelfCreate,
)
from app.services.partner_context import (
    resolve_partner_from_link,
    resolve_partner_user_link,
    update_partner_runtime_fields,
)

router = APIRouter(prefix="/partner", tags=["partner-management-v1"])

PROFILE_MANAGER_ROLES = {
    "PARTNER_OWNER",
    "PARTNER_MANAGER",
    "PARTNER_ACCOUNTANT",
    "PARTNER_SERVICE_MANAGER",
}
LOCATION_MANAGER_ROLES = {
    "PARTNER_OWNER",
    "PARTNER_MANAGER",
    "PARTNER_SERVICE_MANAGER",
}
USER_MANAGER_ROLES = {"PARTNER_OWNER"}


def _user_id_from_token(token: dict) -> str:
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user_context")
    return user_id


def get_current_partner_link(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> PartnerUserRole:
    _user_id_from_token(token)
    link = resolve_partner_user_link(db, claims=token)
    if not link:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    return link


def get_current_partner(
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> Partner:
    partner = resolve_partner_from_link(db, link=link)
    if not partner:
        raise HTTPException(status_code=403, detail="partner_not_linked")
    if partner.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="partner_inactive")
    return partner


def _ensure_any_role(link: PartnerUserRole, allowed_roles: set[str]) -> None:
    roles = {str(role).upper() for role in (link.roles or []) if role}
    if roles.isdisjoint(allowed_roles):
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/self-profile", response_model=PartnerMeOut)
def partner_me(
    partner: Partner = Depends(get_current_partner),
    link: PartnerUserRole = Depends(get_current_partner_link),
) -> PartnerMeOut:
    return PartnerMeOut(
        partner=PartnerOut.model_validate(partner, from_attributes=True),
        my_roles=list(link.roles or []),
    )


@router.patch("/self-profile", response_model=PartnerOut)
def patch_partner_me(
    payload: PartnerMePatch,
    partner: Partner = Depends(get_current_partner),
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerOut:
    _ensure_any_role(link, PROFILE_MANAGER_ROLES)
    next_contacts = payload.contacts if payload.contacts is not None else (partner.contacts or {})
    next_brand_name = payload.brand_name if payload.brand_name is not None else partner.brand_name
    partner = update_partner_runtime_fields(
        db,
        partner_id=str(partner.id),
        brand_name=next_brand_name,
        contacts=next_contacts,
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="partner_not_linked")
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
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    _ensure_any_role(link, LOCATION_MANAGER_ROLES)
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
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    _ensure_any_role(link, LOCATION_MANAGER_ROLES)
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
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerLocationOut:
    _ensure_any_role(link, LOCATION_MANAGER_ROLES)
    row = db.get(PartnerLocation, location_id)
    if not row or str(row.partner_id) != str(partner.id):
        raise HTTPException(status_code=404, detail="location_not_found")
    row.status = "INACTIVE"
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerLocationOut.model_validate(row, from_attributes=True)


@router.get("/users", response_model=list[PartnerUserRoleOut])
def list_my_partner_users(
    partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db),
) -> list[PartnerUserRoleOut]:
    rows = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner.id).all()
    return [PartnerUserRoleOut(user_id=str(row.user_id), roles=list(row.roles or []), created_at=row.created_at) for row in rows]


@router.post("/users", response_model=PartnerUserRoleOut, status_code=201)
def add_my_partner_user(
    payload: PartnerUserRoleSelfCreate,
    partner: Partner = Depends(get_current_partner),
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> PartnerUserRoleOut:
    _ensure_any_role(link, USER_MANAGER_ROLES)
    user_id = payload.user_id or payload.email
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    row = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner.id, PartnerUserRole.user_id == user_id).first()
    if row:
        row.roles = payload.roles
    else:
        row = PartnerUserRole(partner_id=partner.id, user_id=user_id, roles=payload.roles)
    db.add(row)
    db.commit()
    db.refresh(row)
    return PartnerUserRoleOut(user_id=str(row.user_id), roles=list(row.roles or []), created_at=row.created_at)


@router.delete("/users/{user_id}", status_code=200)
def delete_my_partner_user(
    user_id: str,
    partner: Partner = Depends(get_current_partner),
    link: PartnerUserRole = Depends(get_current_partner_link),
    db: Session = Depends(get_db),
) -> None:
    _ensure_any_role(link, USER_MANAGER_ROLES)
    row = db.query(PartnerUserRole).filter(PartnerUserRole.partner_id == partner.id, PartnerUserRole.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="partner_user_not_found")
    db.delete(row)
    db.commit()
    return None


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

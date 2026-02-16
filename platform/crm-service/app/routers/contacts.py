from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps.auth import AuthContext, get_auth_context
from app.models import CRMContact
from app.schemas.contacts import ContactCreate, ContactListOut, ContactOut, ContactUpdate
from app.services.audit_service import audit_create, audit_delete, audit_update

router = APIRouter(prefix="/contacts", tags=["crm-contacts"])


@router.get("", response_model=ContactListOut)
def list_contacts(
    search: str | None = None,
    client_id: str | None = None,
    partner_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    query = select(CRMContact).where(CRMContact.tenant_id == auth.tenant_id)
    if search:
        query = query.where(or_(CRMContact.full_name.ilike(f"%{search}%"), CRMContact.email.ilike(f"%{search}%")))
    if client_id:
        query = query.where(CRMContact.client_id == client_id)
    if partner_id:
        query = query.where(CRMContact.partner_id == partner_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.execute(query.order_by(CRMContact.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return ContactListOut(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=ContactOut)
def create_contact(payload: ContactCreate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    model = CRMContact(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(model)
    db.flush()
    audit_create(db, auth.tenant_id, "contact", model.id, auth.actor, payload.model_dump())
    db.commit()
    db.refresh(model)
    return model


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    item = db.get(CRMContact, contact_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return item


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: str, payload: ContactUpdate, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    item = db.get(CRMContact, contact_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    before = ContactOut.model_validate(item).model_dump(mode="json")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    after = ContactOut.model_validate(item).model_dump(mode="json")
    audit_update(db, auth.tenant_id, "contact", item.id, auth.actor, before, after)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{contact_id}", response_model=ContactOut)
def delete_contact(contact_id: str, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    item = db.get(CRMContact, contact_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    before = ContactOut.model_validate(item).model_dump(mode="json")
    item.status = "deleted"
    audit_delete(db, auth.tenant_id, "contact", item.id, auth.actor, before)
    db.commit()
    db.refresh(item)
    return item

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, update
from sqlalchemy.orm import Session

from app.models.partner import Partner
from app.models.partner_management import PartnerUserRole
from app.services.bootstrap import ensure_demo_partner_binding


def _is_uuid(value: Any) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _claims_user_id(claims: dict[str, Any]) -> str | None:
    user_id = str(claims.get("user_id") or claims.get("sub") or "").strip()
    return user_id or None


def _claims_email(claims: dict[str, Any]) -> str | None:
    email = str(claims.get("email") or claims.get("sub") or "").strip().lower()
    return email or None


def _claims_roles(claims: dict[str, Any]) -> list[str]:
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = claims.get("role")
    if role:
        roles = [*roles, role]
    return [str(item) for item in roles if str(item).strip()]


def resolve_partner_user_link(db: Session, *, claims: dict[str, Any]) -> PartnerUserRole | None:
    user_id = _claims_user_id(claims)
    if not user_id:
        return None

    link = db.query(PartnerUserRole).filter(PartnerUserRole.user_id == user_id).first()
    if link is not None:
        return link

    repaired = ensure_demo_partner_binding(
        db,
        user_id=user_id,
        email=_claims_email(claims),
        roles=_claims_roles(claims),
    )
    if not repaired:
        return None

    return db.query(PartnerUserRole).filter(PartnerUserRole.user_id == user_id).first()


def resolve_partner_id_from_claims(db: Session, *, claims: dict[str, Any]) -> str | None:
    link = resolve_partner_user_link(db, claims=claims)
    if link is not None:
        return str(link.partner_id)

    raw_partner_id = claims.get("partner_id")
    if _is_uuid(raw_partner_id):
        return str(raw_partner_id)
    return None


def resolve_partner_by_id(db: Session, *, partner_id: Any) -> Partner | None:
    if not partner_id:
        return None
    try:
        partner = db.query(Partner).filter(cast(Partner.id, String) == str(partner_id)).first()
    except Exception:
        partner = None
    if partner is not None:
        return partner
    try:
        return db.get(Partner, str(partner_id))
    except Exception:
        return None


def resolve_partner_from_link(db: Session, *, link: PartnerUserRole | None) -> Partner | None:
    if link is None:
        return None
    return resolve_partner_by_id(db, partner_id=link.partner_id)


_UNSET = object()


def update_partner_runtime_fields(
    db: Session,
    *,
    partner_id: str,
    brand_name: str | None | object = _UNSET,
    contacts: dict[str, Any] | None | object = _UNSET,
    status: str | None | object = _UNSET,
) -> Partner | None:
    values: dict[str, Any] = {}
    if brand_name is not _UNSET:
        values["brand_name"] = brand_name
    if contacts is not _UNSET:
        values["contacts"] = contacts or {}
    if status is not _UNSET:
        values["status"] = status
    if not values:
        return resolve_partner_by_id(db, partner_id=partner_id)
    if "updated_at" in Partner.__table__.c:
        values["updated_at"] = func.current_timestamp()

    db.execute(
        update(Partner.__table__)
        .where(cast(Partner.__table__.c.id, String) == str(partner_id))
        .values(**values)
    )
    db.commit()
    db.expire_all()
    return resolve_partner_by_id(db, partner_id=partner_id)


def resolve_partner_from_claims(db: Session, *, claims: dict[str, Any]) -> Partner | None:
    partner_id = resolve_partner_id_from_claims(db, claims=claims)
    return resolve_partner_by_id(db, partner_id=partner_id)


__all__ = [
    "resolve_partner_by_id",
    "resolve_partner_from_claims",
    "resolve_partner_from_link",
    "resolve_partner_id_from_claims",
    "resolve_partner_user_link",
    "update_partner_runtime_fields",
]

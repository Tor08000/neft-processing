from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.audit_retention import AuditLegalHold, AuditLegalHoldScope


def create_legal_hold(
    db: Session,
    *,
    scope: AuditLegalHoldScope,
    case_id: str | None,
    reason: str,
    created_by: str | None,
) -> AuditLegalHold:
    hold = AuditLegalHold(
        scope=scope.value,
        case_id=case_id,
        reason=reason,
        created_by=created_by,
        active=True,
    )
    db.add(hold)
    db.flush()
    return hold


def disable_legal_hold(db: Session, *, hold_id: str) -> AuditLegalHold | None:
    hold = db.query(AuditLegalHold).filter(AuditLegalHold.id == hold_id).one_or_none()
    if not hold:
        return None
    hold.active = False
    db.add(hold)
    db.flush()
    return hold


def list_legal_holds(
    db: Session,
    *,
    case_id: str | None = None,
    active_only: bool = True,
) -> list[AuditLegalHold]:
    query = db.query(AuditLegalHold)
    if active_only:
        query = query.filter(AuditLegalHold.active.is_(True))
    if case_id:
        query = query.filter(AuditLegalHold.case_id == case_id)
    return query.order_by(AuditLegalHold.created_at.desc()).all()


def has_active_legal_hold(db: Session, *, case_id: str | None = None) -> bool:
    query = db.query(AuditLegalHold).filter(AuditLegalHold.active.is_(True))
    if case_id:
        query = query.filter(
            or_(
                AuditLegalHold.scope.in_([
                    AuditLegalHoldScope.GLOBAL.value,
                    AuditLegalHoldScope.ORG.value,
                ]),
                AuditLegalHold.case_id == case_id,
            )
        )
    else:
        query = query.filter(
            AuditLegalHold.scope.in_([
                AuditLegalHoldScope.GLOBAL.value,
                AuditLegalHoldScope.ORG.value,
            ])
        )
    return db.query(query.exists()).scalar() is True


__all__ = [
    "create_legal_hold",
    "disable_legal_hold",
    "list_legal_holds",
    "has_active_legal_hold",
]

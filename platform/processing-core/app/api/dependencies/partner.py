from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.legal_acceptance import LegalSubjectType
from app.services.legal import enforce_legal_gate, subject_from_request
from app.services.partner_auth import require_partner_user
from app.services.partner_context import resolve_partner_id_from_claims


def partner_portal_user(
    request: Request,
    token: dict = Depends(require_partner_user),
    db: Session = Depends(get_db),
) -> dict:
    canonical_partner_id = resolve_partner_id_from_claims(db, claims=token) or token.get("partner_id")
    subject = subject_from_request(
        subject_type=LegalSubjectType.PARTNER,
        subject_id=str(canonical_partner_id),
    )
    roles = token.get("roles") or []
    role = token.get("role")
    if role:
        roles = [*roles, role]
    enforce_legal_gate(db=db, request=request, subject=subject, actor_roles=roles)
    if canonical_partner_id:
        return {**token, "partner_id": str(canonical_partner_id)}
    return token


__all__ = ["partner_portal_user"]

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models.legal_acceptance import LegalSubjectType
from app.services.legal import enforce_legal_gate, subject_from_request


require_client_user = services.client_auth.require_client_user


def client_portal_user(
    request: Request,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> dict:
    """Dependency wrapper to ensure client portal JWT contains client context."""

    subject = subject_from_request(
        subject_type=LegalSubjectType.CLIENT,
        subject_id=str(token.get("client_id")),
    )
    roles = token.get("roles") or []
    role = token.get("role")
    if role:
        roles = [*roles, role]
    enforce_legal_gate(db=db, request=request, subject=subject, actor_roles=roles)
    return token


__all__ = ["client_portal_user"]

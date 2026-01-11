from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.models.legal_acceptance import LegalSubjectType
from app.services.legal import enforce_legal_gate, subject_from_request


require_admin = services.admin_auth.require_admin


def require_admin_user(
    request: Request,
    token: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Dependency wrapper to validate admin JWT tokens.

    This keeps all admin-specific auth enforcement in a dedicated place so it can be
    attached to the admin router prefix without affecting public endpoints.
    """

    subject_id = token.get("user_id") or token.get("sub") or token.get("client_id")
    if subject_id:
        subject = subject_from_request(
            subject_type=LegalSubjectType.USER,
            subject_id=str(subject_id),
        )
        roles = token.get("roles") or []
        role = token.get("role")
        if role:
            roles = [*roles, role]
        enforce_legal_gate(db=db, request=request, subject=subject, actor_roles=roles)
    return token


__all__ = ["require_admin_user"]

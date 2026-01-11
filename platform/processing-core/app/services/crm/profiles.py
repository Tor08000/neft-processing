from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMClientProfile, CRMClientProfileStatus
from app.schemas.crm import CRMClientProfileUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def upsert_profile(
    db: Session,
    *,
    client_id: str,
    payload: CRMClientProfileUpdate,
    request_ctx: RequestContext | None,
) -> CRMClientProfile:
    existing = repository.get_client_profile(db, client_id=client_id)
    if existing is None:
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("status", CRMClientProfileStatus.PROSPECT)
        profile = CRMClientProfile(client_id=client_id, **data)
    else:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        profile = existing
    profile = repository.upsert_client_profile(db, profile)
    events.audit_event(
        db,
        event_type=events.CRM_CLIENT_UPDATED,
        entity_type="crm_client_profile",
        entity_id=str(client_id),
        payload={"status": profile.status.value},
        request_ctx=request_ctx,
    )
    return profile


__all__ = ["upsert_profile"]

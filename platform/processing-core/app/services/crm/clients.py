from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMClient
from app.schemas.crm import CRMClientCreate, CRMClientUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository


def create_client(
    db: Session,
    *,
    payload: CRMClientCreate,
    request_ctx: RequestContext | None,
) -> CRMClient:
    client = CRMClient(
        id=payload.id,
        tenant_id=payload.tenant_id,
        legal_name=payload.legal_name,
        tax_id=payload.tax_id,
        kpp=payload.kpp,
        country=payload.country,
        timezone=payload.timezone,
        status=payload.status,
        meta=payload.meta,
    )
    client = repository.add_client(db, client)
    events.audit_event(
        db,
        event_type=events.CRM_CLIENT_CREATED,
        entity_type="crm_client",
        entity_id=client.id,
        payload={"status": client.status.value},
        request_ctx=request_ctx,
    )
    return client


def update_client(
    db: Session,
    *,
    client: CRMClient,
    payload: CRMClientUpdate,
    request_ctx: RequestContext | None,
) -> CRMClient:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    client = repository.update_client(db, client)
    events.audit_event(
        db,
        event_type=events.CRM_CLIENT_UPDATED,
        entity_type="crm_client",
        entity_id=client.id,
        payload={"status": client.status.value},
        request_ctx=request_ctx,
    )
    return client


__all__ = ["create_client", "update_client"]

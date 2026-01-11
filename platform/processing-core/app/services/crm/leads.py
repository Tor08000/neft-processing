from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMClientProfile, CRMClientProfileStatus, CRMLead, CRMLeadStatus
from app.schemas.crm import CRMLeadCreate, CRMLeadQualifyRequest
from app.services.audit_service import RequestContext
from app.services.crm import clients, events, repository


def create_lead(
    db: Session,
    *,
    payload: CRMLeadCreate,
    request_ctx: RequestContext | None,
) -> CRMLead:
    lead = CRMLead(
        tenant_id=payload.tenant_id,
        source=payload.source,
        status=payload.status,
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        phone=payload.phone,
        email=payload.email,
        comment=payload.comment,
        utm=payload.utm,
        assigned_to=payload.assigned_to,
    )
    lead = repository.add_lead(db, lead)
    events.audit_event(
        db,
        event_type=events.CRM_LEAD_CREATED,
        entity_type="crm_lead",
        entity_id=str(lead.id),
        payload={"status": lead.status.value},
        request_ctx=request_ctx,
    )
    return lead


def qualify_lead(
    db: Session,
    *,
    lead: CRMLead,
    payload: CRMLeadQualifyRequest,
    request_ctx: RequestContext | None,
):
    client = clients.create_client(
        db,
        payload=payload.to_client_payload(lead),
        request_ctx=request_ctx,
    )
    profile = CRMClientProfile(
        client_id=client.id,
        legal_name=payload.legal_name or lead.company_name,
        inn=payload.inn,
        kpp=payload.kpp,
        ogrn=payload.ogrn,
        legal_address=payload.legal_address,
        actual_address=payload.actual_address,
        bank_details=payload.bank_details,
        contacts=payload.contacts,
        roles=payload.roles,
        status=payload.profile_status or CRMClientProfileStatus.PROSPECT,
        risk_level=payload.risk_level,
        tags=payload.tags,
        notes=payload.notes,
    )
    repository.upsert_client_profile(db, profile)
    lead.status = CRMLeadStatus.CONVERTED
    repository.update_lead(db, lead)
    repository.initialize_onboarding_state(db, client_id=client.id)
    events.audit_event(
        db,
        event_type=events.CRM_LEAD_QUALIFIED,
        entity_type="crm_lead",
        entity_id=str(lead.id),
        payload={"client_id": client.id},
        request_ctx=request_ctx,
    )
    return client, profile


__all__ = ["create_lead", "qualify_lead"]

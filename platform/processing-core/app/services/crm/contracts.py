from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMContract, CRMContractStatus
from app.schemas.crm import CRMContractCreate, CRMContractUpdate
from app.services.audit_service import RequestContext
from app.services.crm import events, repository, sync


def create_contract(
    db: Session,
    *,
    client_id: str,
    payload: CRMContractCreate,
    request_ctx: RequestContext | None,
) -> CRMContract:
    contract = CRMContract(
        tenant_id=payload.tenant_id,
        client_id=client_id,
        contract_number=payload.contract_number,
        status=payload.status,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        billing_mode=payload.billing_mode,
        currency=payload.currency,
        risk_profile_id=payload.risk_profile_id,
        limit_profile_id=payload.limit_profile_id,
        documents_required=payload.documents_required,
        meta=payload.meta,
    )
    contract = repository.add_contract(db, contract)
    if contract.status == CRMContractStatus.ACTIVE:
        sync.apply_contract(db, contract=contract, request_ctx=request_ctx)
    return contract


def set_contract_status(
    db: Session,
    *,
    contract: CRMContract,
    status: CRMContractStatus,
    request_ctx: RequestContext | None,
) -> CRMContract:
    previous_version = contract.crm_contract_version
    if contract.status != status:
        contract.crm_contract_version = (contract.crm_contract_version or 0) + 1
        contract.status = status
        contract = repository.update_contract(db, contract)
        events.audit_event(
            db,
            event_type=events.CRM_CONTRACT_VERSION_BUMPED,
            entity_type="crm_contract",
            entity_id=str(contract.id),
            payload={
                "previous_version": previous_version,
                "new_version": contract.crm_contract_version,
                "reason": "status_change",
            },
            request_ctx=request_ctx,
        )
    if status == CRMContractStatus.ACTIVE:
        sync.apply_contract(db, contract=contract, request_ctx=request_ctx)
        events.audit_event(
            db,
            event_type=events.CRM_CONTRACT_ACTIVATED,
            entity_type="crm_contract",
            entity_id=str(contract.id),
            payload={"status": status.value},
            request_ctx=request_ctx,
        )
    elif status == CRMContractStatus.PAUSED:
        sync.disable_contract_features(db, contract=contract, request_ctx=request_ctx)
        events.audit_event(
            db,
            event_type=events.CRM_CONTRACT_PAUSED,
            entity_type="crm_contract",
            entity_id=str(contract.id),
            payload={"status": status.value},
            request_ctx=request_ctx,
        )
    elif status == CRMContractStatus.TERMINATED:
        sync.disable_contract_features(db, contract=contract, request_ctx=request_ctx)
        events.audit_event(
            db,
            event_type=events.CRM_CONTRACT_TERMINATED,
            entity_type="crm_contract",
            entity_id=str(contract.id),
            payload={"status": status.value},
            request_ctx=request_ctx,
        )
    return contract


def update_contract(
    db: Session,
    *,
    contract: CRMContract,
    payload: CRMContractUpdate,
    request_ctx: RequestContext | None,
) -> CRMContract:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contract, field, value)
    contract = repository.update_contract(db, contract)
    events.audit_event(
        db,
        event_type=events.CRM_CONTRACT_UPDATED,
        entity_type="crm_contract",
        entity_id=str(contract.id),
        payload={"status": contract.status.value, "contract_number": contract.contract_number},
        request_ctx=request_ctx,
    )
    return contract


__all__ = ["create_contract", "set_contract_status", "update_contract"]

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.crm import (
    CRMClientStatus,
    CRMContractStatus,
    CRMFeatureFlagType,
    CRMProfileStatus,
    CRMSubscription,
    CRMSubscriptionStatus,
    CRMTariffStatus,
)
from app.schemas.crm import (
    CRMClientCreate,
    CRMClientOut,
    CRMClientUpdate,
    CRMContractCreate,
    CRMContractOut,
    CRMFeatureFlagOut,
    CRMProfileCreate,
    CRMProfileOut,
    CRMRiskProfileCreate,
    CRMRiskProfileOut,
    CRMSubscriptionCreate,
    CRMSubscriptionOut,
    CRMTariffCreate,
    CRMTariffOut,
    CRMTariffUpdate,
)
from app.services.audit_service import request_context_from_request
from app.services.crm import clients, contracts, events, repository, settings, subscriptions, sync, tariffs

router = APIRouter(prefix="/crm", tags=["admin", "crm"])


@router.post("/clients", response_model=CRMClientOut)
def create_client_endpoint(
    request: Request,
    payload: CRMClientCreate,
    db: Session = Depends(get_db),
) -> CRMClientOut:
    ctx = request_context_from_request(request)
    client = clients.create_client(db, payload=payload, request_ctx=ctx)
    return CRMClientOut.model_validate(client)


@router.get("/clients", response_model=list[CRMClientOut])
def list_clients_endpoint(
    tenant_id: int = Query(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMClientOut]:
    items = repository.list_clients(db, tenant_id=tenant_id, limit=limit, offset=offset)
    return [CRMClientOut.model_validate(item) for item in items]


@router.get("/clients/{client_id}", response_model=CRMClientOut)
def get_client_endpoint(
    client_id: str,
    tenant_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> CRMClientOut:
    client = repository.get_client(db, tenant_id=tenant_id, client_id=client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client not found")
    return CRMClientOut.model_validate(client)


@router.patch("/clients/{client_id}", response_model=CRMClientOut)
def update_client_endpoint(
    request: Request,
    client_id: str,
    tenant_id: int = Query(..., ge=1),
    payload: CRMClientUpdate = Body(...),
    db: Session = Depends(get_db),
) -> CRMClientOut:
    client = repository.get_client(db, tenant_id=tenant_id, client_id=client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client not found")
    ctx = request_context_from_request(request)
    updated = clients.update_client(db, client=client, payload=payload, request_ctx=ctx)
    return CRMClientOut.model_validate(updated)


@router.post("/clients/{client_id}/contracts", response_model=CRMContractOut)
def create_contract_endpoint(
    request: Request,
    client_id: str,
    payload: CRMContractCreate,
    db: Session = Depends(get_db),
) -> CRMContractOut:
    ctx = request_context_from_request(request)
    contract = contracts.create_contract(db, client_id=client_id, payload=payload, request_ctx=ctx)
    return CRMContractOut.model_validate(contract)


@router.get("/contracts", response_model=list[CRMContractOut])
def list_contracts_endpoint(
    client_id: str | None = Query(default=None),
    status: CRMContractStatus | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMContractOut]:
    items = repository.list_contracts(db, client_id=client_id, status=status, limit=limit, offset=offset)
    return [CRMContractOut.model_validate(item) for item in items]


@router.post("/contracts/{contract_id}/activate", response_model=CRMContractOut)
def activate_contract_endpoint(
    request: Request,
    contract_id: str,
    db: Session = Depends(get_db),
) -> CRMContractOut:
    contract = repository.get_contract(db, contract_id=contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="contract not found")
    ctx = request_context_from_request(request)
    updated = contracts.set_contract_status(
        db,
        contract=contract,
        status=CRMContractStatus.ACTIVE,
        request_ctx=ctx,
    )
    return CRMContractOut.model_validate(updated)


@router.post("/contracts/{contract_id}/pause", response_model=CRMContractOut)
def pause_contract_endpoint(
    request: Request,
    contract_id: str,
    db: Session = Depends(get_db),
) -> CRMContractOut:
    contract = repository.get_contract(db, contract_id=contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="contract not found")
    ctx = request_context_from_request(request)
    updated = contracts.set_contract_status(
        db,
        contract=contract,
        status=CRMContractStatus.PAUSED,
        request_ctx=ctx,
    )
    return CRMContractOut.model_validate(updated)


@router.post("/contracts/{contract_id}/terminate", response_model=CRMContractOut)
def terminate_contract_endpoint(
    request: Request,
    contract_id: str,
    db: Session = Depends(get_db),
) -> CRMContractOut:
    contract = repository.get_contract(db, contract_id=contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="contract not found")
    ctx = request_context_from_request(request)
    updated = contracts.set_contract_status(
        db,
        contract=contract,
        status=CRMContractStatus.TERMINATED,
        request_ctx=ctx,
    )
    return CRMContractOut.model_validate(updated)


@router.post("/contracts/{contract_id}/apply", response_model=dict)
def apply_contract_endpoint(
    request: Request,
    contract_id: str,
    db: Session = Depends(get_db),
) -> dict:
    contract = repository.get_contract(db, contract_id=contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="contract not found")
    ctx = request_context_from_request(request)
    sync.apply_contract(db, contract=contract, request_ctx=ctx)
    return {"status": "ok", "contract_id": str(contract.id)}


@router.post("/tariffs", response_model=CRMTariffOut)
def create_tariff_endpoint(payload: CRMTariffCreate, db: Session = Depends(get_db)) -> CRMTariffOut:
    tariff = tariffs.create_tariff(db, payload=payload)
    return CRMTariffOut.model_validate(tariff)


@router.get("/tariffs", response_model=list[CRMTariffOut])
def list_tariffs_endpoint(
    status: CRMTariffStatus | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMTariffOut]:
    items = repository.list_tariffs(db, status=status, limit=limit, offset=offset)
    return [CRMTariffOut.model_validate(item) for item in items]


@router.patch("/tariffs/{tariff_id}", response_model=CRMTariffOut)
def update_tariff_endpoint(
    tariff_id: str,
    payload: CRMTariffUpdate,
    db: Session = Depends(get_db),
) -> CRMTariffOut:
    tariff = repository.get_tariff(db, tariff_id=tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="tariff not found")
    updated = tariffs.update_tariff(db, tariff=tariff, payload=payload)
    return CRMTariffOut.model_validate(updated)


@router.post("/clients/{client_id}/subscriptions", response_model=CRMSubscriptionOut)
def create_subscription_endpoint(
    client_id: str,
    payload: CRMSubscriptionCreate,
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = subscriptions.create_subscription(db, client_id=client_id, payload=payload)
    return CRMSubscriptionOut.model_validate(subscription)


@router.get("/subscriptions", response_model=list[CRMSubscriptionOut])
def list_subscriptions_endpoint(
    client_id: str | None = Query(default=None),
    status: CRMSubscriptionStatus | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMSubscriptionOut]:
    items = repository.list_subscriptions(db, client_id=client_id, status=status, limit=limit, offset=offset)
    return [CRMSubscriptionOut.model_validate(item) for item in items]


@router.post("/subscriptions/{subscription_id}/suspend", response_model=CRMSubscriptionOut)
def suspend_subscription_endpoint(
    subscription_id: str,
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    updated = subscriptions.set_subscription_status(
        db,
        subscription=subscription,
        status=CRMSubscriptionStatus.PAUSED,
    )
    return CRMSubscriptionOut.model_validate(updated)


@router.post("/subscriptions/{subscription_id}/resume", response_model=CRMSubscriptionOut)
def resume_subscription_endpoint(
    subscription_id: str,
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    updated = subscriptions.set_subscription_status(
        db,
        subscription=subscription,
        status=CRMSubscriptionStatus.ACTIVE,
    )
    return CRMSubscriptionOut.model_validate(updated)


@router.post("/limit-profiles", response_model=CRMProfileOut)
def create_limit_profile_endpoint(payload: CRMProfileCreate, db: Session = Depends(get_db)) -> CRMProfileOut:
    profile = settings.create_limit_profile(db, payload=payload)
    return CRMProfileOut.model_validate(profile)


@router.get("/limit-profiles", response_model=list[CRMProfileOut])
def list_limit_profiles_endpoint(
    status: CRMProfileStatus | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMProfileOut]:
    items = repository.list_limit_profiles(db, status=status, limit=limit, offset=offset)
    return [CRMProfileOut.model_validate(item) for item in items]


@router.post("/risk-profiles", response_model=CRMRiskProfileOut)
def create_risk_profile_endpoint(payload: CRMRiskProfileCreate, db: Session = Depends(get_db)) -> CRMRiskProfileOut:
    profile = settings.create_risk_profile(db, payload=payload)
    return CRMRiskProfileOut.model_validate(profile)


@router.get("/risk-profiles", response_model=list[CRMRiskProfileOut])
def list_risk_profiles_endpoint(
    status: CRMProfileStatus | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[CRMRiskProfileOut]:
    items = repository.list_risk_profiles(db, status=status, limit=limit, offset=offset)
    return [CRMRiskProfileOut.model_validate(item) for item in items]


@router.get("/clients/{client_id}/features", response_model=list[CRMFeatureFlagOut])
def list_feature_flags_endpoint(
    client_id: str,
    tenant_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> list[CRMFeatureFlagOut]:
    items = repository.list_feature_flags(db, tenant_id=tenant_id, client_id=client_id)
    return [CRMFeatureFlagOut.model_validate(item) for item in items]


@router.post("/clients/{client_id}/features/{feature}/enable", response_model=CRMFeatureFlagOut)
def enable_feature_flag_endpoint(
    request: Request,
    client_id: str,
    feature: CRMFeatureFlagType,
    tenant_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> CRMFeatureFlagOut:
    ctx = request_context_from_request(request)
    record = settings.set_feature_flag(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        feature=feature,
        enabled=True,
        updated_by=ctx.actor_id if ctx else None,
    )
    events.audit_event(
        db,
        event_type=events.CRM_FEATURE_ENABLED,
        entity_type="crm_feature_flag",
        entity_id=f"{client_id}:{feature.value}",
        payload={"enabled": True, "feature": feature.value},
        request_ctx=ctx,
    )
    return CRMFeatureFlagOut.model_validate(record)


@router.post("/clients/{client_id}/features/{feature}/disable", response_model=CRMFeatureFlagOut)
def disable_feature_flag_endpoint(
    request: Request,
    client_id: str,
    feature: CRMFeatureFlagType,
    tenant_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> CRMFeatureFlagOut:
    ctx = request_context_from_request(request)
    record = settings.set_feature_flag(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        feature=feature,
        enabled=False,
        updated_by=ctx.actor_id if ctx else None,
    )
    events.audit_event(
        db,
        event_type=events.CRM_FEATURE_DISABLED,
        entity_type="crm_feature_flag",
        entity_id=f"{client_id}:{feature.value}",
        payload={"enabled": False, "feature": feature.value},
        request_ctx=ctx,
    )
    return CRMFeatureFlagOut.model_validate(record)


__all__ = ["router"]

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.crm import (
    CRMClientStatus,
    CRMContractStatus,
    CRMFeatureFlagType,
    CRMProfileStatus,
    CRMSubscription,
    CRMSubscriptionSegmentReason,
    CRMSubscriptionStatus,
    CRMTariffStatus,
)
from app.schemas.admin.money_flow import SubscriptionCFOExplainResponse
from app.schemas.admin.crm import CRMDecisionContextResponse
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
    CRMSubscriptionChangeTariff,
    CRMSubscriptionOut,
    CRMSubscriptionPreviewCharge,
    CRMSubscriptionPreviewOut,
    CRMSubscriptionPreviewSegment,
    CRMSubscriptionPreviewUsage,
    CRMTariffCreate,
    CRMTariffOut,
    CRMTariffUpdate,
)
from app.security.rbac.guard import require_permission
from app.services.audit_service import request_context_from_request
from app.services.crm import clients, contracts, decision_context, events, repository, settings, subscriptions, sync, tariffs
from app.services.crm.subscription_cfo_explain import build_subscription_cfo_explain
from app.services.crm.subscription_explain import build_explain
from app.services.crm.subscription_pricing_engine import price_subscription_v2
from app.services.crm.subscription_segments import build_segments_v2, record_subscription_change
from app.services.crm.subscription_usage_collector import collect_usage_by_segments

def require_control_plane_version(
    x_crm_version: str | None = Header(default=None, alias="X-CRM-Version"),
) -> None:
    if not x_crm_version:
        raise HTTPException(status_code=409, detail="crm_control_plane_frozen")


router = APIRouter(
    prefix="/crm",
    tags=["admin", "crm"],
    dependencies=[Depends(require_control_plane_version), Depends(require_permission("admin:contracts:*"))],
)


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


@router.get("/clients/{client_id}/decision-context", response_model=CRMDecisionContextResponse)
def get_decision_context_endpoint(
    client_id: str,
    tenant_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> CRMDecisionContextResponse:
    try:
        payload = decision_context.build_decision_context(db, tenant_id=tenant_id, client_id=client_id)
    except decision_context.DecisionContextNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CRMDecisionContextResponse(
        client_id=payload["client_id"],
        tenant_id=payload["tenant_id"],
        active_contract=CRMContractOut.model_validate(payload["active_contract"]) if payload["active_contract"] else None,
        tariff=CRMTariffOut.model_validate(payload["tariff"]) if payload["tariff"] else None,
        feature_flags=[CRMFeatureFlagOut.model_validate(item) for item in payload["feature_flags"]],
        risk_profile=CRMRiskProfileOut.model_validate(payload["risk_profile"]) if payload["risk_profile"] else None,
        limit_profile=CRMProfileOut.model_validate(payload["limit_profile"]) if payload["limit_profile"] else None,
        enforcement_flags=payload["enforcement_flags"],
    )


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
def create_tariff_endpoint(
    request: Request,
    payload: CRMTariffCreate,
    db: Session = Depends(get_db),
) -> CRMTariffOut:
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
    request: Request,
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
    request: Request,
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
    request: Request,
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
    request: Request,
    subscription_id: str,
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    updated = record_subscription_change(
        db,
        subscription=subscription,
        event_type=CRMSubscriptionSegmentReason.RESUME,
        effective_at=datetime.now(timezone.utc),
    )
    return CRMSubscriptionOut.model_validate(updated)


@router.post("/subscriptions/{subscription_id}/preview-billing", response_model=CRMSubscriptionPreviewOut)
def preview_subscription_billing_endpoint(
    subscription_id: str,
    period_id: str = Query(..., description="Billing period id"),
    db: Session = Depends(get_db),
) -> CRMSubscriptionPreviewOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    period = repository.get_billing_period(db, billing_period_id=period_id)
    if not period:
        raise HTTPException(status_code=404, detail="billing period not found")
    tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="tariff not found")
    tariff_definition = tariff.definition or {}
    segments = build_segments_v2(subscription=subscription, period=period)
    fuel_flag = repository.get_feature_flag(
        db,
        tenant_id=subscription.tenant_id,
        client_id=subscription.client_id,
        feature=CRMFeatureFlagType.SUBSCRIPTION_METER_FUEL_ENABLED,
    )
    include_fuel_metrics = bool(fuel_flag.enabled) if fuel_flag else False
    counters = collect_usage_by_segments(
        db,
        subscription=subscription,
        billing_period_id=str(period.id),
        segments=segments,
        include_fuel_metrics=include_fuel_metrics,
    ).counters
    pricing = price_subscription_v2(
        subscription=subscription,
        billing_period_id=str(period.id),
        segments=segments,
        counters=counters,
        tariff_definition=tariff_definition,
        period_start=period.start_at,
        period_end=period.end_at,
    )
    segment_payload = [
        CRMSubscriptionPreviewSegment(
            id=str(segment.id),
            tariff_plan_id=segment.tariff_plan_id,
            segment_start=segment.segment_start,
            segment_end=segment.segment_end,
            status=segment.status.value,
            reason=segment.reason.value if segment.reason else None,
            days_count=segment.days_count,
        )
        for segment in segments
    ]
    explain = build_explain(
        segments=[segment.model_dump() for segment in segment_payload],
        counters=counters,
        charges=pricing.charges,
    )
    usage_payload = [CRMSubscriptionPreviewUsage(**item) for item in explain.usage]
    charges_payload = [
        CRMSubscriptionPreviewCharge(**{key: value for key, value in item.items() if key != "explain"})
        for item in explain.charges
    ]
    return CRMSubscriptionPreviewOut(
        segments=segment_payload,
        usage=usage_payload,
        charges=charges_payload,
        total=explain.total,
    )


@router.get("/subscriptions/{subscription_id}/cfo-explain", response_model=SubscriptionCFOExplainResponse)
def subscription_cfo_explain_endpoint(
    subscription_id: str,
    period_id: str = Query(...),
    db: Session = Depends(get_db),
) -> SubscriptionCFOExplainResponse:
    try:
        payload = build_subscription_cfo_explain(
            db,
            subscription_id=subscription_id,
            billing_period_id=period_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SubscriptionCFOExplainResponse.model_validate(payload)


@router.post("/subscriptions/{subscription_id}/change-tariff", response_model=CRMSubscriptionOut)
def change_subscription_tariff_endpoint(
    request: Request,
    subscription_id: str,
    payload: CRMSubscriptionChangeTariff,
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    current_tariff = repository.get_tariff(db, tariff_id=subscription.tariff_plan_id)
    new_tariff = repository.get_tariff(db, tariff_id=payload.new_tariff_id)
    if not new_tariff:
        raise HTTPException(status_code=404, detail="tariff not found")
    reason = CRMSubscriptionSegmentReason.UPGRADE
    if current_tariff and new_tariff.base_fee_minor < current_tariff.base_fee_minor:
        reason = CRMSubscriptionSegmentReason.DOWNGRADE
    ctx = request_context_from_request(request)
    updated = record_subscription_change(
        db,
        subscription=subscription,
        event_type=reason,
        effective_at=payload.effective_at,
        tariff_plan_id=payload.new_tariff_id,
    )
    events.audit_event(
        db,
        event_type="CRM_SUBSCRIPTION_TARIFF_CHANGED",
        entity_type="crm_subscription",
        entity_id=str(subscription.id),
        payload={"new_tariff_id": payload.new_tariff_id, "effective_at": payload.effective_at.isoformat()},
        request_ctx=ctx,
    )
    return CRMSubscriptionOut.model_validate(updated)


@router.post("/subscriptions/{subscription_id}/pause", response_model=CRMSubscriptionOut)
def pause_subscription_v2_endpoint(
    request: Request,
    subscription_id: str,
    effective_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    ctx = request_context_from_request(request)
    timestamp = effective_at or datetime.now(timezone.utc)
    updated = record_subscription_change(
        db,
        subscription=subscription,
        event_type=CRMSubscriptionSegmentReason.PAUSE,
        effective_at=timestamp,
    )
    events.audit_event(
        db,
        event_type="CRM_SUBSCRIPTION_PAUSED",
        entity_type="crm_subscription",
        entity_id=str(subscription.id),
        payload={"effective_at": timestamp.isoformat()},
        request_ctx=ctx,
    )
    return CRMSubscriptionOut.model_validate(updated)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=CRMSubscriptionOut)
def cancel_subscription_v2_endpoint(
    request: Request,
    subscription_id: str,
    effective_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CRMSubscriptionOut:
    subscription = db.query(CRMSubscription).filter(CRMSubscription.id == subscription_id).one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription not found")
    ctx = request_context_from_request(request)
    timestamp = effective_at or datetime.now(timezone.utc)
    updated = record_subscription_change(
        db,
        subscription=subscription,
        event_type=CRMSubscriptionSegmentReason.CANCEL,
        effective_at=timestamp,
    )
    events.audit_event(
        db,
        event_type="CRM_SUBSCRIPTION_CANCELLED",
        entity_type="crm_subscription",
        entity_id=str(subscription.id),
        payload={"effective_at": timestamp.isoformat()},
        request_ctx=ctx,
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

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod
from app.models.crm import (
    CRMBillingMode,
    CRMClient,
    CRMClientStatus,
    CRMContract,
    CRMContractStatus,
    CRMFeatureFlag,
    CRMFeatureFlagType,
    CRMLimitProfile,
    CRMProfileStatus,
    CRMRiskProfile,
    CRMSubscription,
    CRMSubscriptionCharge,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
    CRMTariffPlan,
    CRMTariffStatus,
    CRMUsageCounter,
)


def add_client(db: Session, client: CRMClient) -> CRMClient:
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def get_client(db: Session, *, tenant_id: int, client_id: str) -> CRMClient | None:
    return (
        db.query(CRMClient)
        .filter(CRMClient.tenant_id == tenant_id)
        .filter(CRMClient.id == client_id)
        .one_or_none()
    )


def list_clients(db: Session, *, tenant_id: int, limit: int = 50, offset: int = 0) -> list[CRMClient]:
    return (
        db.query(CRMClient)
        .filter(CRMClient.tenant_id == tenant_id)
        .order_by(CRMClient.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_client(db: Session, client: CRMClient) -> CRMClient:
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def add_contract(db: Session, contract: CRMContract) -> CRMContract:
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def get_contract(db: Session, *, contract_id: str) -> CRMContract | None:
    return db.query(CRMContract).filter(CRMContract.id == contract_id).one_or_none()


def list_contracts(
    db: Session,
    *,
    client_id: str | None = None,
    status: CRMContractStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CRMContract]:
    query = db.query(CRMContract)
    if client_id:
        query = query.filter(CRMContract.client_id == client_id)
    if status:
        query = query.filter(CRMContract.status == status)
    return query.order_by(CRMContract.created_at.desc()).offset(offset).limit(limit).all()


def update_contract(db: Session, contract: CRMContract) -> CRMContract:
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def add_tariff(db: Session, tariff: CRMTariffPlan) -> CRMTariffPlan:
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return tariff


def list_tariffs(
    db: Session,
    *,
    status: CRMTariffStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CRMTariffPlan]:
    query = db.query(CRMTariffPlan)
    if status:
        query = query.filter(CRMTariffPlan.status == status)
    return query.order_by(CRMTariffPlan.created_at.desc()).offset(offset).limit(limit).all()


def get_tariff(db: Session, *, tariff_id: str) -> CRMTariffPlan | None:
    return db.query(CRMTariffPlan).filter(CRMTariffPlan.id == tariff_id).one_or_none()


def get_billing_period(db: Session, *, billing_period_id: str) -> BillingPeriod | None:
    return db.query(BillingPeriod).filter(BillingPeriod.id == billing_period_id).one_or_none()


def update_tariff(db: Session, tariff: CRMTariffPlan) -> CRMTariffPlan:
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return tariff


def add_subscription(db: Session, subscription: CRMSubscription) -> CRMSubscription:
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def list_subscriptions(
    db: Session,
    *,
    client_id: str | None = None,
    status: CRMSubscriptionStatus | Iterable[CRMSubscriptionStatus] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CRMSubscription]:
    query = db.query(CRMSubscription)
    if client_id:
        query = query.filter(CRMSubscription.client_id == client_id)
    if status:
        if isinstance(status, CRMSubscriptionStatus):
            query = query.filter(CRMSubscription.status == status)
        else:
            query = query.filter(CRMSubscription.status.in_(set(status)))
    return query.order_by(CRMSubscription.started_at.desc()).offset(offset).limit(limit).all()


def update_subscription(db: Session, subscription: CRMSubscription) -> CRMSubscription:
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def add_subscription_charge(
    db: Session,
    charge: CRMSubscriptionCharge,
    *,
    auto_commit: bool = True,
) -> CRMSubscriptionCharge:
    db.add(charge)
    if auto_commit:
        db.commit()
        db.refresh(charge)
    return charge


def add_subscription_segment(
    db: Session,
    segment: CRMSubscriptionPeriodSegment,
    *,
    auto_commit: bool = True,
) -> CRMSubscriptionPeriodSegment:
    db.add(segment)
    if auto_commit:
        db.commit()
        db.refresh(segment)
    return segment


def list_subscription_segments(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    status: CRMSubscriptionSegmentStatus | None = None,
) -> list[CRMSubscriptionPeriodSegment]:
    query = (
        db.query(CRMSubscriptionPeriodSegment)
        .filter(CRMSubscriptionPeriodSegment.subscription_id == subscription_id)
        .filter(CRMSubscriptionPeriodSegment.billing_period_id == billing_period_id)
    )
    if status:
        query = query.filter(CRMSubscriptionPeriodSegment.status == status)
    return query.order_by(CRMSubscriptionPeriodSegment.segment_start.asc()).all()


def list_subscription_charges(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
) -> list[CRMSubscriptionCharge]:
    return (
        db.query(CRMSubscriptionCharge)
        .filter(CRMSubscriptionCharge.subscription_id == subscription_id)
        .filter(CRMSubscriptionCharge.billing_period_id == billing_period_id)
        .order_by(CRMSubscriptionCharge.created_at.asc())
        .all()
    )


def get_subscription_charge_by_key(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
    charge_key: str,
) -> CRMSubscriptionCharge | None:
    return (
        db.query(CRMSubscriptionCharge)
        .filter(CRMSubscriptionCharge.subscription_id == subscription_id)
        .filter(CRMSubscriptionCharge.billing_period_id == billing_period_id)
        .filter(CRMSubscriptionCharge.charge_key == charge_key)
        .one_or_none()
    )


def add_usage_counter(
    db: Session,
    counter: CRMUsageCounter,
    *,
    auto_commit: bool = True,
) -> CRMUsageCounter:
    db.add(counter)
    if auto_commit:
        db.commit()
        db.refresh(counter)
    return counter


def list_usage_counters(
    db: Session,
    *,
    subscription_id: str,
    billing_period_id: str,
) -> list[CRMUsageCounter]:
    return (
        db.query(CRMUsageCounter)
        .filter(CRMUsageCounter.subscription_id == subscription_id)
        .filter(CRMUsageCounter.billing_period_id == billing_period_id)
        .order_by(CRMUsageCounter.created_at.asc())
        .all()
    )


def add_limit_profile(db: Session, profile: CRMLimitProfile) -> CRMLimitProfile:
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def list_limit_profiles(
    db: Session,
    *,
    status: CRMProfileStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CRMLimitProfile]:
    query = db.query(CRMLimitProfile)
    if status:
        query = query.filter(CRMLimitProfile.status == status)
    return query.order_by(CRMLimitProfile.created_at.desc()).offset(offset).limit(limit).all()


def get_limit_profile(db: Session, *, profile_id: str) -> CRMLimitProfile | None:
    return db.query(CRMLimitProfile).filter(CRMLimitProfile.id == profile_id).one_or_none()


def add_risk_profile(db: Session, profile: CRMRiskProfile) -> CRMRiskProfile:
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def list_risk_profiles(
    db: Session,
    *,
    status: CRMProfileStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CRMRiskProfile]:
    query = db.query(CRMRiskProfile)
    if status:
        query = query.filter(CRMRiskProfile.status == status)
    return query.order_by(CRMRiskProfile.created_at.desc()).offset(offset).limit(limit).all()


def get_risk_profile(db: Session, *, profile_id: str) -> CRMRiskProfile | None:
    return db.query(CRMRiskProfile).filter(CRMRiskProfile.id == profile_id).one_or_none()


def get_active_subscription(db: Session, *, client_id: str) -> CRMSubscription | None:
    return (
        db.query(CRMSubscription)
        .filter(CRMSubscription.client_id == client_id)
        .filter(CRMSubscription.status == CRMSubscriptionStatus.ACTIVE)
        .order_by(CRMSubscription.started_at.desc())
        .first()
    )


def get_feature_flag(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    feature: CRMFeatureFlagType,
) -> CRMFeatureFlag | None:
    return (
        db.query(CRMFeatureFlag)
        .filter(CRMFeatureFlag.tenant_id == tenant_id)
        .filter(CRMFeatureFlag.client_id == client_id)
        .filter(CRMFeatureFlag.feature == feature)
        .one_or_none()
    )


def list_feature_flags(db: Session, *, tenant_id: int, client_id: str) -> list[CRMFeatureFlag]:
    return (
        db.query(CRMFeatureFlag)
        .filter(CRMFeatureFlag.tenant_id == tenant_id)
        .filter(CRMFeatureFlag.client_id == client_id)
        .order_by(CRMFeatureFlag.feature.asc())
        .all()
    )


def set_feature_flag(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    feature: CRMFeatureFlagType,
    enabled: bool,
    updated_by: str | None,
) -> CRMFeatureFlag:
    record = get_feature_flag(db, tenant_id=tenant_id, client_id=client_id, feature=feature)
    if record is None:
        record = CRMFeatureFlag(
            tenant_id=tenant_id,
            client_id=client_id,
            feature=feature,
            enabled=enabled,
            updated_by=updated_by,
        )
    else:
        record.enabled = enabled
        record.updated_by = updated_by
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_billing_mode_for_contracts(
    db: Session, *, contract_ids: Iterable[str], billing_mode: CRMBillingMode
) -> None:
    if not contract_ids:
        return
    db.query(CRMContract).filter(CRMContract.id.in_(set(contract_ids))).update(
        {CRMContract.billing_mode: billing_mode}, synchronize_session="fetch"
    )
    db.commit()


__all__ = [
    "add_client",
    "add_contract",
    "add_limit_profile",
    "add_risk_profile",
    "add_subscription",
    "add_subscription_charge",
    "add_subscription_segment",
    "add_tariff",
    "add_usage_counter",
    "get_active_subscription",
    "get_billing_period",
    "get_client",
    "get_contract",
    "get_feature_flag",
    "get_limit_profile",
    "get_risk_profile",
    "get_tariff",
    "list_clients",
    "list_contracts",
    "list_feature_flags",
    "list_limit_profiles",
    "list_risk_profiles",
    "list_subscriptions",
    "list_subscription_charges",
    "list_subscription_segments",
    "list_usage_counters",
    "get_subscription_charge_by_key",
    "list_tariffs",
    "set_feature_flag",
    "update_client",
    "update_contract",
    "update_subscription",
    "update_tariff",
]

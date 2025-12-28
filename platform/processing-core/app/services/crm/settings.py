from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.crm import CRMLimitProfile, CRMFeatureFlagType, CRMRiskProfile
from app.schemas.crm import CRMProfileCreate, CRMRiskProfileCreate
from app.services.crm import repository


def create_limit_profile(db: Session, *, payload: CRMProfileCreate) -> CRMLimitProfile:
    profile = CRMLimitProfile(
        tenant_id=payload.tenant_id,
        name=payload.name,
        status=payload.status,
        definition=payload.definition,
    )
    return repository.add_limit_profile(db, profile)


def create_risk_profile(db: Session, *, payload: CRMRiskProfileCreate) -> CRMRiskProfile:
    meta = payload.meta or {}
    if payload.definition:
        meta = {**meta, "definition": payload.definition}
    profile = CRMRiskProfile(
        tenant_id=payload.tenant_id,
        name=payload.name,
        status=payload.status,
        risk_policy_id=payload.risk_policy_id,
        threshold_set_id=payload.threshold_set_id,
        shadow_enabled=payload.shadow_enabled,
        meta=meta or None,
    )
    return repository.add_risk_profile(db, profile)


def set_feature_flag(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    feature: CRMFeatureFlagType,
    enabled: bool,
    updated_by: str | None,
):
    return repository.set_feature_flag(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        feature=feature,
        enabled=enabled,
        updated_by=updated_by,
    )


__all__ = ["create_limit_profile", "create_risk_profile", "set_feature_flag"]

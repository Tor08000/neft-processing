from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.unified_rule import (
    RuleSetActive,
    RuleSetStatus,
    RuleSetVersion,
    UnifiedRule,
    UnifiedRuleMetric,
    UnifiedRulePolicy,
    UnifiedRuleScope,
)
from app.schemas.unified_rules import RuleSetVersionCreate, RuleSetVersionOut, UnifiedRuleCreate, UnifiedRuleOut
from app.services.unified_rules_engine import validate_conflicts


router = APIRouter(prefix="/api/v1/admin/rules", tags=["admin-rules"])
canonical_router = APIRouter(
    prefix="/v1/admin/rules",
    tags=["admin-rules"],
    dependencies=[Depends(require_admin_user)],
)


@router.post("/versions", response_model=RuleSetVersionOut, status_code=201)
def create_rule_set_version(
    payload: RuleSetVersionCreate,
    db: Session = Depends(get_db),
) -> RuleSetVersionOut:
    version = RuleSetVersion(
        name=payload.name,
        scope=payload.scope,
        status=RuleSetStatus.DRAFT,
        created_at=datetime.now(timezone.utc),
        notes=payload.notes,
        parent_version_id=payload.parent_version_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return RuleSetVersionOut.model_validate(version)


@router.get("/versions", response_model=list[RuleSetVersionOut])
def list_rule_set_versions(
    scope: UnifiedRuleScope | None = Query(None),
    db: Session = Depends(get_db),
) -> list[RuleSetVersionOut]:
    query = db.query(RuleSetVersion)
    if scope:
        query = query.filter(RuleSetVersion.scope == scope)
    versions = query.order_by(RuleSetVersion.id.desc()).all()
    return [RuleSetVersionOut.model_validate(version) for version in versions]


@router.post("/versions/{version_id}/publish")
def publish_rule_set_version(
    version_id: int,
    db: Session = Depends(get_db),
) -> dict:
    version = db.query(RuleSetVersion).filter(RuleSetVersion.id == version_id).one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="version_not_found")
    rules = db.query(UnifiedRule).filter(UnifiedRule.version_id == version.id).all()
    conflicts = validate_conflicts(rules)
    if conflicts:
        raise HTTPException(status_code=409, detail={"conflicts": conflicts})
    version.status = RuleSetStatus.PUBLISHED
    version.published_at = datetime.now(timezone.utc)
    db.add(version)
    db.commit()
    return {"status": "ok"}


@router.post("/versions/{version_id}/activate")
def activate_rule_set_version(
    version_id: int,
    db: Session = Depends(get_db),
) -> dict:
    version = db.query(RuleSetVersion).filter(RuleSetVersion.id == version_id).one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="version_not_found")
    version.status = RuleSetStatus.ACTIVE
    version.activated_at = datetime.now(timezone.utc)
    active = db.query(RuleSetActive).filter(RuleSetActive.scope == version.scope).one_or_none()
    if active:
        active.version_id = version.id
        active.activated_at = datetime.now(timezone.utc)
    else:
        active = RuleSetActive(scope=version.scope, version_id=version.id)
    db.add(active)
    db.add(version)
    db.commit()
    return {"status": "ok"}


@router.post("/rules", response_model=UnifiedRuleOut, status_code=201)
def create_unified_rule(
    payload: UnifiedRuleCreate,
    version_id: int = Query(..., alias="version_id"),
    db: Session = Depends(get_db),
) -> UnifiedRuleOut:
    version = db.query(RuleSetVersion).filter(RuleSetVersion.id == version_id).one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="version_not_found")
    rule = UnifiedRule(
        code=payload.code,
        version_id=version.id,
        scope=payload.scope,
        selector=payload.selector,
        window=payload.window,
        metric=UnifiedRuleMetric(payload.metric) if payload.metric else None,
        value=payload.value,
        policy=UnifiedRulePolicy(payload.policy),
        priority=payload.priority,
        reason_code=payload.reason_code,
        explain_template=payload.explain_template,
        tags=payload.tags,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return UnifiedRuleOut.model_validate(rule)


@canonical_router.post("/versions", response_model=RuleSetVersionOut, status_code=201)
def create_rule_set_version_canonical(
    payload: RuleSetVersionCreate,
    db: Session = Depends(get_db),
) -> RuleSetVersionOut:
    return create_rule_set_version(payload=payload, db=db)


@canonical_router.get("/versions", response_model=list[RuleSetVersionOut])
def list_rule_set_versions_canonical(
    scope: UnifiedRuleScope | None = Query(None),
    db: Session = Depends(get_db),
) -> list[RuleSetVersionOut]:
    return list_rule_set_versions(scope=scope, db=db)


@canonical_router.post("/versions/{version_id}/publish")
def publish_rule_set_version_canonical(version_id: int, db: Session = Depends(get_db)) -> dict:
    return publish_rule_set_version(version_id=version_id, db=db)


@canonical_router.post("/versions/{version_id}/activate")
def activate_rule_set_version_canonical(version_id: int, db: Session = Depends(get_db)) -> dict:
    return activate_rule_set_version(version_id=version_id, db=db)


@canonical_router.post("/rules", response_model=UnifiedRuleOut, status_code=201)
def create_unified_rule_canonical(
    payload: UnifiedRuleCreate,
    version_id: int = Query(..., alias="version_id"),
    db: Session = Depends(get_db),
) -> UnifiedRuleOut:
    return create_unified_rule(payload=payload, version_id=version_id, db=db)

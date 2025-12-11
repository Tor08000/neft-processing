from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.risk_rule import RiskRule, RiskRuleAuditAction, RiskRuleScope
from app.repositories.risk_rules_repository import RiskRulesRepository
from app.schemas.admin.risk_rules import (
    RiskRuleCreate,
    RiskRuleListResponse,
    RiskRuleRead,
    RiskRuleUpdate,
)
from app.services.risk_rules import MetricType, RuleConfig, RuleScope


router = APIRouter(prefix="/risk", tags=["admin"])


def _get_rule_or_404(db: Session, rule_id: int) -> RiskRule:
    rule = db.query(RiskRule).filter(RiskRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="risk rule not found")
    return rule


def _serialize_rule(rule: RiskRule) -> RiskRuleRead:
    config = RuleConfig.model_validate(rule.dsl_payload)
    return RiskRuleRead(
        id=rule.id,
        description=rule.description,
        enabled=rule.enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        version=len(rule.versions),
        dsl=config,
    )


def _validate_config(config: RuleConfig) -> None:
    if config.scope != RuleScope.GLOBAL and not config.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subject_id is required for scoped rules",
        )

    if config.metric in {MetricType.COUNT, MetricType.TOTAL_AMOUNT} and not config.window:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="window must be provided for aggregated metrics",
        )

    if config.selector.hours is not None and len(set(config.selector.hours)) != len(
        config.selector.hours
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selector.hours must not contain duplicates",
        )


def _extract_actor(token: dict | None) -> str | None:
    if not token:
        return None
    return token.get("email") or token.get("sub") or token.get("user_id")


def _with_validated_config(
    operation: Callable[[RiskRulesRepository, RuleConfig], RiskRule],
    *,
    db: Session,
    body: RiskRuleCreate | RiskRuleUpdate,
    performed_by: str | None,
) -> RiskRule:
    config = RuleConfig.model_validate(body.dsl.model_dump())
    _validate_config(config)
    repository = RiskRulesRepository(db, performed_by=performed_by)
    try:
        return operation(repository, config)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="risk rule not found")


@router.get("/rules", response_model=RiskRuleListResponse)
def list_risk_rules(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    scope: RuleScope | None = None,
    subject_ref: str | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
) -> RiskRuleListResponse:
    query = db.query(RiskRule)

    if scope is not None:
        query = query.filter(RiskRule.scope == RiskRuleScope(scope.value))
    if subject_ref is not None:
        query = query.filter(RiskRule.subject_ref == subject_ref)
    if enabled is not None:
        query = query.filter(RiskRule.enabled == enabled)

    total = query.count()
    items = (
        query.order_by(RiskRule.priority.asc(), RiskRule.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    serialized = [_serialize_rule(rule) for rule in items]
    return RiskRuleListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/rules/{rule_id}", response_model=RiskRuleRead)
def get_risk_rule(rule_id: int, db: Session = Depends(get_db)) -> RiskRuleRead:
    rule = _get_rule_or_404(db, rule_id)
    return _serialize_rule(rule)


@router.post("/rules", response_model=RiskRuleRead, status_code=status.HTTP_201_CREATED)
def create_risk_rule(
    body: RiskRuleCreate,
    db: Session = Depends(get_db),
    admin_token: dict = Depends(require_admin_user),
) -> RiskRuleRead:
    actor = _extract_actor(admin_token)
    rule = _with_validated_config(
        lambda repo, cfg: repo.create_rule(
            cfg,
            description=body.description,
            performed_by=repo.performed_by,
        ),
        db=db,
        body=body,
        performed_by=actor,
    )
    return _serialize_rule(rule)


@router.put("/rules/{rule_id}", response_model=RiskRuleRead)
def update_risk_rule(
    rule_id: int,
    body: RiskRuleUpdate,
    db: Session = Depends(get_db),
    admin_token: dict = Depends(require_admin_user),
) -> RiskRuleRead:
    actor = _extract_actor(admin_token)

    def _update(repo: RiskRulesRepository, cfg: RuleConfig) -> RiskRule:
        return repo.update_rule(
            rule_id,
            cfg,
            description=body.description,
            performed_by=repo.performed_by,
        )

    rule = _with_validated_config(
        _update,
        db=db,
        body=body,
        performed_by=actor,
    )
    return _serialize_rule(rule)


@router.post("/rules/{rule_id}/enable", response_model=RiskRuleRead)
def enable_risk_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    admin_token: dict = Depends(require_admin_user),
) -> RiskRuleRead:
    actor = _extract_actor(admin_token)
    rule = _get_rule_or_404(db, rule_id)
    body = RiskRuleUpdate(description=rule.description, dsl=RuleConfig.model_validate(rule.dsl_payload))
    body.dsl.enabled = True
    updated = _with_validated_config(
        lambda repo, cfg: repo.update_rule(
            rule_id,
            cfg,
            description=body.description,
            performed_by=repo.performed_by,
            audit_action=RiskRuleAuditAction.ENABLE,
        ),
        db=db,
        body=body,
        performed_by=actor,
    )
    return _serialize_rule(updated)


@router.post("/rules/{rule_id}/disable", response_model=RiskRuleRead)
def disable_risk_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    admin_token: dict = Depends(require_admin_user),
) -> RiskRuleRead:
    actor = _extract_actor(admin_token)
    rule = _get_rule_or_404(db, rule_id)
    body = RiskRuleUpdate(description=rule.description, dsl=RuleConfig.model_validate(rule.dsl_payload))
    body.dsl.enabled = False
    updated = _with_validated_config(
        lambda repo, cfg: repo.update_rule(
            rule_id,
            cfg,
            description=body.description,
            performed_by=repo.performed_by,
            audit_action=RiskRuleAuditAction.DISABLE,
        ),
        db=db,
        body=body,
        performed_by=actor,
    )
    return _serialize_rule(updated)


__all__ = ["router"]


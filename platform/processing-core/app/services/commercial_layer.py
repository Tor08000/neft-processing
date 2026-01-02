from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.commercial_layer import CommercialPlan, PlanFeature, PlanFeatureCode, UsageMetric
from app.models.subscriptions_v1 import ClientSubscription, SubscriptionStatus
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class LimitEvaluation:
    metric: UsageMetric
    used: Decimal
    limit: Decimal | None
    overage: Decimal | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_active_subscription(db: Session, *, client_id: str) -> ClientSubscription | None:
    return (
        db.query(ClientSubscription)
        .filter(ClientSubscription.client_id == client_id)
        .order_by(ClientSubscription.created_at.desc())
        .first()
    )


def get_plan(db: Session, *, plan_id: str) -> CommercialPlan | None:
    try:
        plan_uuid = uuid.UUID(str(plan_id))
    except ValueError:
        return None
    return db.query(CommercialPlan).filter(CommercialPlan.id == plan_uuid).one_or_none()


def get_plan_features(db: Session, *, plan_id: str) -> list[PlanFeature]:
    return (
        db.query(PlanFeature)
        .filter(PlanFeature.plan_id == plan_id)
        .order_by(PlanFeature.feature.asc())
        .all()
    )


def resolve_limit(plan_features: Iterable[PlanFeature], metric: UsageMetric) -> Decimal | None:
    lookup = {
        UsageMetric.CARDS_ACTIVE: "cards",
        UsageMetric.TRANSACTIONS: "transactions",
        UsageMetric.ALERTS_SENT: "alerts",
        UsageMetric.EXPORTS: "exports",
    }
    key = lookup.get(metric)
    if not key:
        return None
    for feature in plan_features:
        if feature.limits and key in feature.limits:
            return Decimal(str(feature.limits.get(key)))
    return None


def require_plan_feature(
    db: Session,
    *,
    client_id: str,
    feature: PlanFeatureCode,
    request_ctx: RequestContext | None = None,
) -> None:
    subscription = get_active_subscription(db, client_id=client_id)
    if not subscription:
        raise HTTPException(status_code=403, detail="missing_subscription")

    plan = get_plan(db, plan_id=str(subscription.plan_id))
    if not plan:
        raise HTTPException(status_code=403, detail="missing_plan")

    plan_feature = (
        db.query(PlanFeature)
        .filter(PlanFeature.plan_id == plan.id, PlanFeature.feature == feature)
        .one_or_none()
    )

    if not plan_feature or not plan_feature.enabled:
        AuditService(db).audit(
            event_type="PLAN_LIMIT_EXCEEDED",
            entity_type="client",
            entity_id=str(client_id),
            action="feature_blocked",
            visibility=AuditVisibility.INTERNAL,
            reason=f"feature:{feature}",
            request_ctx=request_ctx,
        )
        raise HTTPException(status_code=403, detail="upgrade_plan")


def require_plan_limit(
    db: Session,
    *,
    client_id: str,
    metric: UsageMetric,
    used_value: Decimal,
    request_ctx: RequestContext | None = None,
) -> None:
    subscription = get_active_subscription(db, client_id=client_id)
    if not subscription:
        raise HTTPException(status_code=403, detail="missing_subscription")

    plan = get_plan(db, plan_id=str(subscription.plan_id))
    if not plan:
        raise HTTPException(status_code=403, detail="missing_plan")

    features = get_plan_features(db, plan_id=str(plan.id))
    limit_value = resolve_limit(features, metric)
    if limit_value is not None and used_value > limit_value:
        AuditService(db).audit(
            event_type="PLAN_LIMIT_EXCEEDED",
            entity_type="client",
            entity_id=str(client_id),
            action="limit_exceeded",
            visibility=AuditVisibility.INTERNAL,
            reason=f"metric:{metric}",
            after={"limit": str(limit_value), "value": str(used_value)},
            request_ctx=request_ctx,
        )
        raise HTTPException(status_code=403, detail="upgrade_plan")


def build_limit_evaluations(
    *,
    plan_features: Iterable[PlanFeature],
    usage_values: dict[UsageMetric, Decimal],
) -> list[LimitEvaluation]:
    results: list[LimitEvaluation] = []
    for metric, used in usage_values.items():
        limit_value = resolve_limit(plan_features, metric)
        overage = None
        if limit_value is not None and used > limit_value:
            overage = used - limit_value
        results.append(LimitEvaluation(metric=metric, used=used, limit=limit_value, overage=overage))
    return results


def create_pending_subscription(
    db: Session,
    *,
    client_id: str,
    tenant_id: int,
    plan_id: str,
    billing_account_id: str | None,
    audit_event_id: str | None,
) -> ClientSubscription:
    subscription = ClientSubscription(
        tenant_id=tenant_id,
        client_id=client_id,
        plan_id=plan_id,
        status=SubscriptionStatus.PENDING,
        start_at=_now(),
        end_at=None,
        auto_renew=False,
        billing_account_id=billing_account_id,
        audit_event_id=audit_event_id,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

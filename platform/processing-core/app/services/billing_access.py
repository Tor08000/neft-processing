from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.audit_log import ActorType, AuditVisibility
from app.services.audit_service import AuditService, RequestContext, request_context_from_request
from app.services.entitlements_v2_service import (
    AVAILABILITY_ADDON,
    AVAILABILITY_DISABLED,
    AVAILABILITY_ENABLED,
    get_org_entitlements_snapshot,
)


class BillingActionKind(str, Enum):
    READ_ONLY = "READ_ONLY"
    WRITE = "WRITE"
    EXPORT_CREATE = "EXPORT_CREATE"
    EXPORT_DOWNLOAD = "EXPORT_DOWNLOAD"
    INTEGRATION_OUTBOUND = "INTEGRATION_OUTBOUND"
    SCHEDULE_TRIGGER = "SCHEDULE_TRIGGER"


class BillingBlockMode(str, Enum):
    SOFT = "soft"
    HARD = "hard"


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    error_code: str | None
    message: str | None
    feature_key: str | None
    subscription_status: str | None
    block_mode: BillingBlockMode | None


ERROR_MESSAGES = {
    "billing_soft_blocked": "Функция недоступна из-за задолженности. Оплатите счёт или смените тариф.",
    "billing_hard_blocked": "Доступ временно приостановлен. Оплатите счёт или обратитесь в поддержку.",
    "feature_not_entitled": "Функция недоступна для текущего тарифа.",
    "addon_required": "Требуется дополнительный модуль или аддон для этой функции.",
}


def _normalize_subscription_status(status: str | None) -> str | None:
    if not status:
        return None
    upper = str(status).upper()
    if upper in {"PAST_DUE", "OVERDUE"}:
        return "OVERDUE"
    if upper == "SUSPENDED":
        return "SUSPENDED"
    if upper == "ACTIVE":
        return "ACTIVE"
    return upper


def billing_policy_allow(action_kind: BillingActionKind, subscription_status: str | None) -> bool:
    if not subscription_status or subscription_status == "ACTIVE":
        return True
    if subscription_status == "OVERDUE":
        return action_kind in {BillingActionKind.READ_ONLY, BillingActionKind.EXPORT_DOWNLOAD}
    if subscription_status == "SUSPENDED":
        return action_kind == BillingActionKind.READ_ONLY
    return True


def get_subscription_status(db: Session, *, org_id: int) -> str | None:
    snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
    subscription = snapshot.entitlements.get("subscription") or {}
    return _normalize_subscription_status(subscription.get("status"))


def _resolve_org_id(token: dict) -> int:
    org_id = token.get("client_id") or token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="missing_org")
    try:
        return int(org_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="invalid_org")


def _feature_available(availability: str | None) -> bool:
    return availability in {AVAILABILITY_ENABLED, "LIMITED"}


def _feature_decision(features: dict[str, dict[str, str]], feature_keys: Iterable[str]) -> EntitlementDecision:
    feature_key = next(iter(feature_keys), None)
    if not feature_key:
        return EntitlementDecision(
            allowed=True,
            error_code=None,
            message=None,
            feature_key=None,
            subscription_status=None,
            block_mode=None,
        )

    seen_addon = False
    for key in feature_keys:
        payload = features.get(key) or {}
        availability = payload.get("availability")
        if _feature_available(availability):
            return EntitlementDecision(
                allowed=True,
                error_code=None,
                message=None,
                feature_key=key,
                subscription_status=None,
                block_mode=None,
            )
        if availability == AVAILABILITY_ADDON:
            seen_addon = True

    error_code = "feature_not_entitled"
    return EntitlementDecision(
        allowed=False,
        error_code=error_code,
        message=ERROR_MESSAGES["addon_required"] if seen_addon else ERROR_MESSAGES["feature_not_entitled"],
        feature_key=feature_key,
        subscription_status=None,
        block_mode=None,
    )


def _billing_decision(subscription_status: str | None) -> EntitlementDecision:
    if subscription_status == "OVERDUE":
        return EntitlementDecision(
            allowed=False,
            error_code="billing_soft_blocked",
            message=ERROR_MESSAGES["billing_soft_blocked"],
            feature_key=None,
            subscription_status=subscription_status,
            block_mode=BillingBlockMode.SOFT,
        )
    if subscription_status == "SUSPENDED":
        return EntitlementDecision(
            allowed=False,
            error_code="billing_hard_blocked",
            message=ERROR_MESSAGES["billing_hard_blocked"],
            feature_key=None,
            subscription_status=subscription_status,
            block_mode=BillingBlockMode.HARD,
        )
    return EntitlementDecision(
        allowed=True,
        error_code=None,
        message=None,
        feature_key=None,
        subscription_status=subscription_status,
        block_mode=None,
    )


def evaluate_entitlement(
    db: Session,
    *,
    token: dict,
    feature_keys: Iterable[str] | None,
    action_kind: BillingActionKind,
    mode: str = "hard",
) -> EntitlementDecision:
    _ = mode
    org_id = _resolve_org_id(token)
    snapshot = get_org_entitlements_snapshot(db, org_id=org_id)
    features = snapshot.entitlements.get("features") or {}
    subscription_status = _normalize_subscription_status(
        (snapshot.entitlements.get("subscription") or {}).get("status")
    )
    if feature_keys:
        feature_decision = _feature_decision(features, feature_keys)
        if not feature_decision.allowed:
            return EntitlementDecision(
                allowed=False,
                error_code=feature_decision.error_code,
                message=feature_decision.message,
                feature_key=feature_decision.feature_key,
                subscription_status=subscription_status,
                block_mode=feature_decision.block_mode,
            )

    if not billing_policy_allow(action_kind, subscription_status):
        return _billing_decision(subscription_status)

    return EntitlementDecision(
        allowed=True,
        error_code=None,
        message=None,
        feature_key=None,
        subscription_status=subscription_status,
        block_mode=None,
    )


def decision_payload(decision: EntitlementDecision, *, feature_key: str | None) -> dict:
    return {
        "error": decision.error_code,
        "feature_key": feature_key or decision.feature_key,
        "subscription_status": decision.subscription_status,
        "message": decision.message,
    }


def audit_billing_blocked(
    db: Session,
    *,
    request: Request | None,
    token: dict | None,
    org_id: int | None,
    subscription_status: str | None,
    feature_key: str | None,
    action_kind: BillingActionKind,
    block_mode: BillingBlockMode | None,
) -> None:
    if org_id is None:
        return
    ctx = request_context_from_request(request, token=token)
    if ctx.actor_type == ActorType.SYSTEM and token is None:
        ctx = RequestContext(actor_type=ActorType.SERVICE, actor_id="billing_guard")
    AuditService(db).audit(
        event_type="billing_blocked",
        entity_type="billing",
        entity_id=str(org_id),
        action="billing_blocked",
        visibility=AuditVisibility.INTERNAL,
        after={
            "org_id": str(org_id),
            "user_id": (token.get("user_id") or token.get("sub")) if token else None,
            "subscription_status": subscription_status,
            "feature_key": feature_key,
            "endpoint": request.url.path if request else None,
            "action_kind": action_kind.value,
            "block_mode": block_mode.value if block_mode else None,
        },
        request_ctx=ctx,
    )


def enforce_entitlement(
    db: Session,
    *,
    request: Request | None,
    token: dict,
    feature_keys: Iterable[str] | None,
    action_kind: BillingActionKind,
    mode: str = "hard",
) -> None:
    decision = evaluate_entitlement(
        db,
        token=token,
        feature_keys=feature_keys,
        action_kind=action_kind,
        mode=mode,
    )
    if decision.allowed:
        return
    org_id = None
    try:
        org_id = _resolve_org_id(token)
    except HTTPException:
        org_id = None
    if decision.error_code in {"billing_soft_blocked", "billing_hard_blocked"}:
        audit_billing_blocked(
            db,
            request=request,
            token=token,
            org_id=org_id,
            subscription_status=decision.subscription_status,
            feature_key=decision.feature_key,
            action_kind=action_kind,
            block_mode=decision.block_mode,
        )
    raise HTTPException(status_code=403, detail=decision_payload(decision, feature_key=decision.feature_key))


def require_entitlement(
    feature_key: str,
    *,
    mode: str = "hard",
    action_kind: BillingActionKind = BillingActionKind.WRITE,
):
    def dep(
        request: Request,
        db: Session,
        token: dict,
    ) -> None:
        enforce_entitlement(
            db,
            request=request,
            token=token,
            feature_keys=[feature_key],
            action_kind=action_kind,
            mode=mode,
        )

    return dep


__all__ = [
    "BillingActionKind",
    "BillingBlockMode",
    "EntitlementDecision",
    "ERROR_MESSAGES",
    "audit_billing_blocked",
    "billing_policy_allow",
    "decision_payload",
    "enforce_entitlement",
    "evaluate_entitlement",
    "get_subscription_status",
    "require_entitlement",
]

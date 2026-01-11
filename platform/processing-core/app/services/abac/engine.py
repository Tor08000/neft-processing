from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from app.models.abac import AbacPolicy, AbacPolicyEffect, AbacPolicyVersion, AbacPolicyVersionStatus


@dataclass(frozen=True)
class AbacPrincipal:
    type: str
    user_id: str | None
    client_id: str | None
    partner_id: str | None
    service_name: str | None
    roles: set[str]
    scopes: set[str]
    region: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class AbacResource:
    type: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class AbacContext:
    ip: str | None
    region: str | None
    timestamp: datetime
    risk: dict[str, Any] | None = None


@dataclass(frozen=True)
class AbacDecision:
    allowed: bool
    reason_code: str | None
    matched_policies: list[dict[str, Any]]
    explain: dict[str, Any]


def _get_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _evaluate_operator(operator: str, operands: list[Any], context: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    left = operands[0] if operands else None
    right = operands[1] if len(operands) > 1 else None

    def resolve(value: Any) -> Any:
        if isinstance(value, str) and "." in value:
            return _get_value(context, value)
        return value

    left_value = resolve(left)
    right_value = resolve(right)

    result = False
    if operator == "eq":
        result = left_value == right_value
    elif operator == "neq":
        result = left_value != right_value
    elif operator == "in":
        result = left_value in (right_value or [])
    elif operator == "nin":
        result = left_value not in (right_value or [])
    elif operator == "lt":
        result = left_value is not None and right_value is not None and left_value < right_value
    elif operator == "lte":
        result = left_value is not None and right_value is not None and left_value <= right_value
    elif operator == "gt":
        result = left_value is not None and right_value is not None and left_value > right_value
    elif operator == "gte":
        result = left_value is not None and right_value is not None and left_value >= right_value
    elif operator == "exists":
        result = left_value is not None
    elif operator == "starts_with":
        if left_value is not None and right_value is not None:
            result = str(left_value).startswith(str(right_value))
    elif operator == "matches":
        if left_value is not None and right_value is not None:
            pattern = str(right_value)
            if len(pattern) > 256:
                result = False
            else:
                result = re.search(pattern, str(left_value)) is not None
    elif operator == "contains":
        if isinstance(left_value, Iterable) and not isinstance(left_value, (str, bytes)):
            result = right_value in left_value

    return result, {
        "op": operator,
        "left": left,
        "right": right,
        "left_value": left_value,
        "right_value": right_value,
        "result": result,
    }


def evaluate_condition(condition: dict[str, Any], context: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if not condition:
        return True, {"result": True, "empty": True}

    if "all" in condition:
        results = [evaluate_condition(item, context) for item in condition["all"]]
        result = all(item[0] for item in results)
        return result, {"op": "all", "result": result, "children": [item[1] for item in results]}
    if "any" in condition:
        results = [evaluate_condition(item, context) for item in condition["any"]]
        result = any(item[0] for item in results)
        return result, {"op": "any", "result": result, "children": [item[1] for item in results]}
    if "not" in condition:
        inner_result, inner_explain = evaluate_condition(condition["not"], context)
        result = not inner_result
        return result, {"op": "not", "result": result, "child": inner_explain}

    for operator in (
        "eq",
        "neq",
        "in",
        "nin",
        "lt",
        "lte",
        "gt",
        "gte",
        "exists",
        "starts_with",
        "matches",
        "contains",
    ):
        if operator in condition:
            operands = condition[operator]
            if not isinstance(operands, list):
                operands = [operands]
            return _evaluate_operator(operator, operands, context)

    return False, {"result": False, "error": "unsupported_condition"}


class AbacEngine:
    def __init__(self, db):
        self.db = db

    def _active_version(self) -> AbacPolicyVersion | None:
        return (
            self.db.query(AbacPolicyVersion)
            .filter(AbacPolicyVersion.status == AbacPolicyVersionStatus.ACTIVE)
            .order_by(AbacPolicyVersion.activated_at.desc(), AbacPolicyVersion.created_at.desc())
            .first()
        )

    def _policies_for_action(self, version_id: str, action: str, resource_type: str) -> list[AbacPolicy]:
        policies = (
            self.db.query(AbacPolicy)
            .filter(AbacPolicy.version_id == version_id)
            .filter(AbacPolicy.resource_type == resource_type)
            .order_by(AbacPolicy.priority.desc())
            .all()
        )
        return [policy for policy in policies if action in (policy.actions or [])]

    def evaluate(
        self,
        *,
        principal: AbacPrincipal,
        action: str,
        resource: AbacResource,
        entitlements: dict[str, Any],
        context: AbacContext,
    ) -> AbacDecision:
        version = self._active_version()
        if not version:
            return AbacDecision(False, "abac_no_active_version", [], {"result": False, "reason": "no_active"})

        policies = self._policies_for_action(version.id, action, resource.type)
        eval_context = {
            "principal": {
                "type": principal.type,
                "user_id": principal.user_id,
                "client_id": principal.client_id,
                "partner_id": principal.partner_id,
                "service_name": principal.service_name,
                "roles": sorted(principal.roles),
                "scopes": sorted(principal.scopes),
                "region": principal.region,
            },
            "resource": resource.attributes,
            "entitlements": entitlements,
            "context": {
                "ip": context.ip,
                "region": context.region,
                "ts": context.timestamp.isoformat(),
                "risk": context.risk or {},
            },
        }

        matched: list[dict[str, Any]] = []
        best_policy: AbacPolicy | None = None
        best_explain: dict[str, Any] | None = None
        best_result: bool | None = None

        for policy in policies:
            result, explain = evaluate_condition(policy.condition or {}, eval_context)
            if not result:
                continue
            matched.append(
                {
                    "code": policy.code,
                    "effect": policy.effect.value,
                    "priority": policy.priority,
                    "reason_code": policy.reason_code,
                }
            )
            if best_policy is None or policy.priority > best_policy.priority:
                best_policy = policy
                best_explain = explain
                best_result = policy.effect == AbacPolicyEffect.ALLOW
            elif policy.priority == best_policy.priority:
                if policy.effect == AbacPolicyEffect.DENY:
                    best_policy = policy
                    best_explain = explain
                    best_result = False

        if not best_policy:
            return AbacDecision(False, "abac_default_deny", matched, {"result": False, "reason": "no_match"})

        allowed = bool(best_result)
        reason_code = best_policy.reason_code
        return AbacDecision(
            allowed,
            reason_code,
            matched,
            {
                "result": allowed,
                "policy": best_policy.code,
                "effect": best_policy.effect.value,
                "priority": best_policy.priority,
                "condition": best_explain,
            },
        )


__all__ = [
    "AbacContext",
    "AbacDecision",
    "AbacEngine",
    "AbacPrincipal",
    "AbacResource",
    "evaluate_condition",
]

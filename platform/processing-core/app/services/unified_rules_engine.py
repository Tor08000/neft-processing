from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.operation import Operation
from app.models.unified_rule import (
    RuleSetActive,
    RuleSetVersion,
    UnifiedRule,
    UnifiedRuleMetric,
    UnifiedRulePolicy,
    UnifiedRuleScope,
)
from app.schemas.unified_rules import RuleEvaluationContext, RuleWindowConfig, RuleValueConfig


PolicyDecision = UnifiedRulePolicy


POLICY_SEVERITY = {
    UnifiedRulePolicy.HARD_DECLINE: 100,
    UnifiedRulePolicy.SOFT_DECLINE: 90,
    UnifiedRulePolicy.REVIEW: 80,
    UnifiedRulePolicy.THROTTLE: 70,
    UnifiedRulePolicy.STEP_UP_AUTH: 60,
    UnifiedRulePolicy.APPLY_LIMIT: 50,
    UnifiedRulePolicy.APPLY_DISCOUNT: 40,
    UnifiedRulePolicy.ALLOW: 10,
}

INCOMPATIBLE_POLICIES: set[tuple[UnifiedRulePolicy, UnifiedRulePolicy]] = {
    (UnifiedRulePolicy.HARD_DECLINE, UnifiedRulePolicy.APPLY_DISCOUNT),
    (UnifiedRulePolicy.APPLY_DISCOUNT, UnifiedRulePolicy.HARD_DECLINE),
    (UnifiedRulePolicy.ALLOW, UnifiedRulePolicy.THROTTLE),
    (UnifiedRulePolicy.THROTTLE, UnifiedRulePolicy.ALLOW),
    (UnifiedRulePolicy.APPLY_LIMIT, UnifiedRulePolicy.ALLOW),
    (UnifiedRulePolicy.ALLOW, UnifiedRulePolicy.APPLY_LIMIT),
}


@dataclass(frozen=True)
class MatchedRule:
    rule: UnifiedRule
    metric_value: float | int | None
    triggered: bool
    explain: str | None


class MetricsProvider:
    def get_metric(
        self,
        metric: UnifiedRuleMetric,
        window: RuleWindowConfig | None,
        context: RuleEvaluationContext,
    ) -> float:
        raise NotImplementedError


class SyntheticMetricsProvider(MetricsProvider):
    def __init__(self, metrics: dict[str, float | int]) -> None:
        self._metrics = metrics

    def get_metric(
        self,
        metric: UnifiedRuleMetric,
        window: RuleWindowConfig | None,
        context: RuleEvaluationContext,
    ) -> float:
        key = metric.value
        return float(self._metrics.get(key, 0))


class OperationsMetricsProvider(MetricsProvider):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_metric(
        self,
        metric: UnifiedRuleMetric,
        window: RuleWindowConfig | None,
        context: RuleEvaluationContext,
    ) -> float:
        if metric not in {UnifiedRuleMetric.COUNT, UnifiedRuleMetric.AMOUNT}:
            return 0.0
        if window is None:
            return 0.0
        start_at, end_at = _window_bounds(window, context.timestamp)
        query = self._db.query(Operation).filter(Operation.created_at >= start_at).filter(
            Operation.created_at <= end_at
        )
        if context.subject.client_id:
            query = query.filter(Operation.client_id == context.subject.client_id)
        if context.object.card_id:
            query = query.filter(Operation.card_id == context.object.card_id)
        if metric == UnifiedRuleMetric.COUNT:
            return float(query.count())
        amount = query.with_entities(func.coalesce(func.sum(Operation.amount), 0)).scalar()
        return float(amount or 0)


def _window_bounds(window: RuleWindowConfig, timestamp: datetime) -> tuple[datetime, datetime]:
    tz = timezone.utc if window.timezone in (None, "UTC") else timezone.utc
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=tz)
    if window.type == "rolling":
        if window.unit == "minute":
            delta = timedelta(minutes=window.size)
        elif window.unit == "hour":
            delta = timedelta(hours=window.size)
        elif window.unit == "day":
            delta = timedelta(days=window.size)
        else:
            delta = timedelta(days=30 * window.size)
        return timestamp - delta, timestamp
    if window.unit == "month":
        start = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = _add_months(start, window.size) - timedelta(microseconds=1)
        return start, end
    if window.unit == "day":
        start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=window.size) - timedelta(microseconds=1)
        return start, end
    if window.unit == "hour":
        start = timestamp.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=window.size) - timedelta(microseconds=1)
        return start, end
    start = timestamp.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=window.size) - timedelta(microseconds=1)
    return start, end


def _add_months(start: datetime, months: int) -> datetime:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    return start.replace(year=year, month=month)


def selector_matches(selector: dict[str, Any] | None, context: RuleEvaluationContext) -> bool:
    if not selector:
        return True
    lookup = {
        **context.subject.model_dump(exclude_none=True),
        **context.object.model_dump(exclude_none=True),
    }
    for key, expected in selector.items():
        actual = lookup.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        else:
            if actual != expected:
                return False
    return True


def _compare_value(op: str, current: float, threshold: float) -> bool:
    if op in ("<", "<="):
        return current <= threshold if op == "<=" else current < threshold
    if op in (">", ">="):
        return current >= threshold if op == ">=" else current > threshold
    if op in ("==", "="):
        return current == threshold
    if op == "!=":
        return current != threshold
    return False


def _triggered(value_cfg: RuleValueConfig | None, current: float) -> bool:
    if value_cfg is None or value_cfg.threshold is None:
        return True
    op = value_cfg.op
    compare = _compare_value(op, current, float(value_cfg.threshold))
    if op in ("<", "<="):
        return not compare
    return compare


def evaluate_rules(
    rules: Iterable[UnifiedRule],
    context: RuleEvaluationContext,
    metrics_provider: MetricsProvider,
) -> list[MatchedRule]:
    matched: list[MatchedRule] = []
    for rule in rules:
        if rule.scope not in (UnifiedRuleScope.GLOBAL, context.scope):
            continue
        if not selector_matches(rule.selector or {}, context):
            continue
        window = RuleWindowConfig.model_validate(rule.window) if rule.window else None
        value_cfg = RuleValueConfig.model_validate(rule.value) if rule.value else None
        current = 0.0
        if rule.metric:
            current = metrics_provider.get_metric(rule.metric, window, context)
            if rule.metric in (UnifiedRuleMetric.AMOUNT, UnifiedRuleMetric.COUNT):
                attempt = 1.0 if rule.metric == UnifiedRuleMetric.COUNT else float(
                    context.object.amount or 0
                )
                current += attempt
        elif context.object.amount is not None:
            current = float(context.object.amount)
        triggered = _triggered(value_cfg, current)
        if not triggered:
            continue
        explain = None
        if rule.explain_template:
            explain = rule.explain_template.format(current=current, threshold=value_cfg.threshold if value_cfg else None)
        elif value_cfg and value_cfg.threshold is not None:
            explain = f"{current} {value_cfg.op} {value_cfg.threshold}"
        matched.append(MatchedRule(rule=rule, metric_value=current, triggered=triggered, explain=explain))
    return matched


def resolve_decision(matched: list[MatchedRule]) -> tuple[PolicyDecision, list[MatchedRule]]:
    if not matched:
        return UnifiedRulePolicy.ALLOW, []
    ordered = sorted(
        matched,
        key=lambda item: (
            -POLICY_SEVERITY.get(item.rule.policy, 0),
            -item.rule.priority,
            -len(item.rule.selector or {}),
            item.rule.created_at or datetime.min.replace(tzinfo=timezone.utc),
            item.rule.code,
        ),
    )
    return ordered[0].rule.policy, ordered


def get_active_version(db: Session, scope: UnifiedRuleScope) -> RuleSetVersion | None:
    active = db.query(RuleSetActive).filter(RuleSetActive.scope == scope).one_or_none()
    if active:
        return db.query(RuleSetVersion).filter(RuleSetVersion.id == active.version_id).one_or_none()
    return (
        db.query(RuleSetVersion)
        .filter(RuleSetVersion.scope == scope)
        .order_by(RuleSetVersion.id.desc())
        .first()
    )


def evaluate_with_db(
    db: Session,
    context: RuleEvaluationContext,
    *,
    version_id: int | None = None,
) -> tuple[PolicyDecision, list[MatchedRule], RuleSetVersion | None]:
    version = (
        db.query(RuleSetVersion).filter(RuleSetVersion.id == version_id).one_or_none()
        if version_id
        else get_active_version(db, context.scope)
    )
    if version is None:
        return UnifiedRulePolicy.ALLOW, [], None
    rules = (
        db.query(UnifiedRule)
        .filter(UnifiedRule.version_id == version.id)
        .order_by(UnifiedRule.priority.desc(), UnifiedRule.id.asc())
        .all()
    )
    matched = evaluate_rules(rules, context, OperationsMetricsProvider(db))
    decision, ordered = resolve_decision(matched)
    return decision, ordered, version


def validate_conflicts(rules: list[UnifiedRule]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for idx, left in enumerate(rules):
        for right in rules[idx + 1 :]:
            if left.scope != right.scope and UnifiedRuleScope.GLOBAL not in (left.scope, right.scope):
                continue
            if left.priority != right.priority:
                continue
            if (left.policy, right.policy) not in INCOMPATIBLE_POLICIES:
                continue
            if selectors_overlap(left.selector or {}, right.selector or {}):
                conflicts.append(
                    {
                        "left": left.code,
                        "right": right.code,
                        "reason": "same selector overlap, incompatible policies",
                        "suggestion": "increase priority or split selector",
                    }
                )
    return conflicts


def selectors_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in set(left.keys()) | set(right.keys()):
        if key not in left or key not in right:
            continue
        left_val = left[key]
        right_val = right[key]
        left_vals = left_val if isinstance(left_val, list) else [left_val]
        right_vals = right_val if isinstance(right_val, list) else [right_val]
        if set(left_vals).isdisjoint(set(right_vals)):
            return False
    return True
